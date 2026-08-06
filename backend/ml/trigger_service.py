from __future__ import annotations

import argparse
import hashlib
import json
import threading
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

from .config import TrainingConfig
from .predict import load_bundle, predict_record
from .safety import apply_safety_rules


_LOG_LOCK = threading.Lock()


def build_dry_run_recommendation(model_dir: str | Path, record: dict) -> dict:
    model_prediction = predict_record(model_dir, record)
    return build_dry_run_recommendation_from_prediction(
        model_dir, record, model_prediction
    )


def build_dry_run_recommendation_from_prediction(
    model_dir: str | Path,
    record: dict,
    model_prediction: dict,
) -> dict:
    bundle = load_bundle(model_dir)
    allowed = {field.name for field in fields(TrainingConfig)}
    config = TrainingConfig(
        **{key: value for key, value in bundle["config"].items() if key in allowed}
    )

    safety_input = {
        "predicted_ventilation": model_prediction["predicted_ventilation"],
        "predicted_occupancy": model_prediction["predicted_occupancy"],
        "occupancy_confidence": model_prediction["confidence"],
        "empty_probability": model_prediction["empty_room"]["empty_probability"],
        "empty_safety_validated": model_prediction["empty_room"]["safety_validated"],
        "overcrowding_risk": model_prediction["overcrowding"]["overcrowding_risk"],
    }
    safety = apply_safety_rules(safety_input, record, config)

    return {
        "prediction_time": model_prediction["prediction_time"],
        "forecast_time": model_prediction["forecast_time"],
        "predicted_occupancy": model_prediction["predicted_occupancy"],
        "prediction_interval": model_prediction["prediction_interval"],
        "occupancy_confidence": model_prediction["confidence"],
        "predicted_ventilation": safety["predicted_ventilation"],
        "overcrowding_risk": model_prediction["overcrowding"]["overcrowding_risk"],
        "overcrowding_probability": model_prediction["overcrowding"]["risk_probability"],
        "empty_probability": model_prediction["empty_room"]["empty_probability"],
        "predicted_empty_duration_minutes": model_prediction["empty_room"][
            "predicted_empty_duration_minutes"
        ],
        "ble_activity_side": model_prediction["ble_activity_side"],
        "recommended_actions": safety["recommended_actions"],
        "warnings": safety["warnings"],
        "automatic_actions_allowed": safety["automatic_actions_allowed"],
        "manual_review_required": not safety["automatic_actions_allowed"],
        "dry_run": True,
        "hardware_commands_sent": False,
        "model_version": model_prediction["model_version"],
    }


def append_recommendation_log(
    model_dir: str | Path,
    record: dict,
    recommendation: dict,
) -> Path:
    path = Path(model_dir) / "recommendation_log.jsonl"
    canonical_input = json.dumps(record, sort_keys=True, default=str).encode("utf-8")
    entry = {
        "logged_at": datetime.now(timezone.utc).isoformat(),
        "input_sha256": hashlib.sha256(canonical_input).hexdigest(),
        "prediction_time": recommendation["prediction_time"],
        "forecast_time": recommendation["forecast_time"],
        "predicted_occupancy": recommendation["predicted_occupancy"],
        "predicted_ventilation": recommendation["predicted_ventilation"],
        "recommended_actions": recommendation["recommended_actions"],
        "warnings": recommendation["warnings"],
        "dry_run": True,
        "hardware_commands_sent": False,
    }
    with _LOG_LOCK:
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry, sort_keys=True) + "\n")
    return path


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate safe dry-run recommendations")
    parser.add_argument("--model-dir", required=True)
    parser.add_argument("--input", required=True)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Accepted for clarity; hardware execution is not implemented",
    )
    parser.add_argument("--no-log", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    record = payload.get("sensor_window", payload)
    if not isinstance(record, dict):
        raise ValueError("Input JSON must be an object or contain sensor_window")

    recommendation = build_dry_run_recommendation(args.model_dir, record)
    if not args.no_log:
        append_recommendation_log(args.model_dir, record, recommendation)
    print(json.dumps(recommendation, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
