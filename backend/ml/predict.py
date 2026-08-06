from __future__ import annotations

import argparse
import json
import math
import sys
import threading
from dataclasses import fields
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd

from .baselines import ventilation_rule
from .config import (
    DERIVED_FORECAST_FEATURE,
    TIMEZONE,
    TrainingConfig,
)
from .features import (
    ble_activity_side,
    missing_feature_ratio,
    record_to_feature_frame,
)
from .schemas import EmptyRoomForecast, OccupancyForecast, OvercrowdingForecast, PredictionInterval


_BUNDLE_CACHE: dict[Path, tuple[int, dict]] = {}
_BUNDLE_CACHE_LOCK = threading.Lock()
_REQUIRED_BUNDLE_SECTIONS = {
    "model_version",
    "config",
    "feature_names",
    "occupancy",
    "ventilation",
    "overcrowding",
    "empty_30m",
    "empty_60m",
}


def load_bundle(model_dir: str | Path) -> dict:
    path = (Path(model_dir) / "model_bundle.joblib").resolve()
    if not path.exists():
        raise FileNotFoundError(f"Model bundle not found: {path}")
    repository_root = str(Path(__file__).resolve().parents[2])
    if repository_root not in sys.path:
        sys.path.insert(0, repository_root)
    modified = path.stat().st_mtime_ns
    with _BUNDLE_CACHE_LOCK:
        cached = _BUNDLE_CACHE.get(path)
        if cached is not None and cached[0] == modified:
            return cached[1]
        bundle = joblib.load(path)
        if not isinstance(bundle, dict):
            raise ValueError("Invalid predictive occupancy model bundle")
        missing = sorted(_REQUIRED_BUNDLE_SECTIONS - set(bundle))
        if missing:
            raise ValueError(
                "Model bundle is missing section(s): " + ", ".join(missing)
            )
        for section in (
            "occupancy",
            "ventilation",
            "overcrowding",
            "empty_30m",
            "empty_60m",
        ):
            if not isinstance(bundle[section], dict):
                raise ValueError(f"Model bundle section {section} must be an object")
        if not isinstance(bundle["config"], dict) or not isinstance(
            bundle["feature_names"], list
        ):
            raise ValueError("Model bundle config or feature contract is invalid")
        _BUNDLE_CACHE[path] = (modified, bundle)
    return bundle


def clear_bundle_cache() -> None:
    with _BUNDLE_CACHE_LOCK:
        _BUNDLE_CACHE.clear()


def predict_record(model_dir: str | Path, record: dict) -> dict:
    bundle = load_bundle(model_dir)
    config = _config_from_bundle(bundle)
    feature_names = bundle["feature_names"]
    features = record_to_feature_frame(record, feature_names)

    occupancy_estimator = bundle["occupancy"]["estimator"]
    raw_occupancy = float(occupancy_estimator.predict(features)[0])
    clipped = float(np.clip(raw_occupancy, 0, config.maximum_predicted_occupancy))
    predicted_occupancy = int(round(clipped))

    interval_half_width = float(bundle["occupancy"]["interval_half_width"])
    lower = int(max(0, math.floor(clipped - interval_half_width)))
    upper = int(
        min(config.maximum_predicted_occupancy, math.ceil(clipped + interval_half_width))
    )
    confidence = _confidence(bundle, record)

    prediction_time = _prediction_time(record)
    forecast_time = prediction_time + timedelta(minutes=30)
    occupancy_forecast = OccupancyForecast(
        prediction_time=prediction_time.isoformat(),
        forecast_time=forecast_time.isoformat(),
        predicted_occupancy=predicted_occupancy,
        prediction_interval=PredictionInterval(lower=lower, upper=upper),
        confidence=confidence,
    )

    task_features = features.copy()
    task_features[DERIVED_FORECAST_FEATURE] = [clipped]
    ventilation = _ventilation_prediction(bundle, task_features, record, clipped)
    overcrowding = _overcrowding_prediction(
        bundle, task_features, predicted_occupancy, config
    )
    empty_30_probability = _binary_probability(
        bundle["empty_30m"]["estimator"], task_features
    )
    empty_60_probability = _binary_probability(
        bundle["empty_60m"]["estimator"], task_features
    )
    empty_30 = empty_30_probability >= float(bundle["empty_30m"]["threshold"])
    empty_60 = empty_60_probability >= float(bundle["empty_60m"]["threshold"])
    duration = 60 if empty_60 else 30 if empty_30 else 0
    empty_safety_validated = bool(
        bundle["empty_30m"].get("safety_validated", False)
        and bundle["empty_60m"].get("safety_validated", False)
    )
    empty_actions = (
        ["REDUCE_VENTILATION", "ENABLE_ENERGY_SAVING_MODE"]
        if predicted_occupancy == 0
        and max(empty_30_probability, empty_60_probability)
        >= config.empty_probability_threshold
        and empty_safety_validated
        else []
    )
    empty_forecast = EmptyRoomForecast(
        forecast_minutes=60,
        empty_probability=round(float(empty_60_probability), 4),
        predicted_empty_duration_minutes=duration,
        recommended_actions=empty_actions,
    )

    result = occupancy_forecast.to_dict()
    result.update(
        {
            "predicted_ventilation": ventilation,
            "overcrowding": overcrowding.to_dict(),
            "empty_room": {
                **empty_forecast.to_dict(),
                "empty_probability_30m": round(float(empty_30_probability), 4),
                "decision_threshold_30m": float(bundle["empty_30m"]["threshold"]),
                "decision_threshold_60m": float(bundle["empty_60m"]["threshold"]),
                "safety_validated": empty_safety_validated,
            },
            "ble_activity_side": ble_activity_side(record),
            "model_version": bundle["model_version"],
        }
    )
    return result


def _ventilation_prediction(
    bundle: dict,
    task_features: pd.DataFrame,
    record: dict,
    predicted_occupancy: float,
) -> str:
    task = bundle["ventilation"]
    if task["kind"] == "rule":
        co2 = record.get("co2_mean_ppm")
        co2_value = float(co2) if co2 is not None else 0.0
        return str(ventilation_rule([predicted_occupancy], [co2_value])[0])
    return str(task["estimator"].predict(task_features)[0])


def _overcrowding_prediction(
    bundle: dict,
    task_features: pd.DataFrame,
    predicted_occupancy: int,
    config: TrainingConfig,
) -> OvercrowdingForecast:
    task = bundle["overcrowding"]
    model_probability = _binary_probability(task["estimator"], task_features)
    capacity_probability = 1.0 / (
        1.0 + math.exp(-(predicted_occupancy - config.room_capacity) / 3.0)
    )
    if task["kind"] == "rule":
        probability = capacity_probability
        risk = predicted_occupancy > config.room_capacity
    else:
        probability = max(model_probability, capacity_probability)
        risk = (
            probability >= float(task["threshold"])
            or predicted_occupancy > config.room_capacity
        )
    return OvercrowdingForecast(
        predicted_occupancy=predicted_occupancy,
        room_capacity=config.room_capacity,
        overcrowding_risk=bool(risk),
        risk_probability=round(float(probability), 4),
        recommended_action="SHOW_CAPACITY_WARNING" if risk else "NONE",
    )


def _binary_probability(estimator, frame: pd.DataFrame) -> float:
    probabilities = estimator.predict_proba(frame)
    classes = list(estimator.classes_)
    if 1 not in classes:
        return 0.0
    return float(probabilities[0, classes.index(1)])


def _confidence(bundle: dict, record: dict) -> float:
    confidence = float(bundle["occupancy"]["base_confidence"])
    confidence *= 1.0 - min(missing_feature_ratio(record) * 0.6, 0.4)
    if _truthy(record.get("radar_stale_flag")):
        confidence *= 0.9
    if _truthy(record.get("co2_stale_flag")):
        confidence *= 0.9
    if _truthy(record.get("pir_stale_flag")):
        confidence *= 0.85
    return round(float(np.clip(confidence, 0.0, 0.99)), 4)


def _prediction_time(record: dict) -> datetime:
    raw = record.get("window_end") or record.get("prediction_time")
    if raw:
        timestamp = pd.Timestamp(raw).to_pydatetime()
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=ZoneInfo(TIMEZONE))
        return timestamp.astimezone(ZoneInfo(TIMEZONE))
    return datetime.now(ZoneInfo(TIMEZONE))


def _config_from_bundle(bundle: dict) -> TrainingConfig:
    allowed = {field.name for field in fields(TrainingConfig)}
    values = {key: value for key, value in bundle["config"].items() if key in allowed}
    return TrainingConfig(**values)


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "stale"}
    return bool(value)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Predict occupancy 30 minutes ahead")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--input", required=True, help="JSON sensor-window file")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    record = payload.get("sensor_window", payload)
    if not isinstance(record, dict):
        raise ValueError("Input JSON must be an object or contain sensor_window")
    print(json.dumps(predict_record(args.model_dir, record), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
