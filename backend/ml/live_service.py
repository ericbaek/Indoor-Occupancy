from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from flask import current_app

try:
    from app.database import (
        get_latest_ml_prediction,
        get_ml_predictions,
        upsert_ml_prediction,
    )
except ModuleNotFoundError:
    from backend.app.database import (
        get_latest_ml_prediction,
        get_ml_predictions,
        upsert_ml_prediction,
    )

from .api_service import require_model
from .api_validation import extract_and_validate_payload
from .predict import predict_record
from .sensor_aggregation import aggregate_sensor_window
from .trigger_service import (
    append_recommendation_log,
    build_dry_run_recommendation_from_prediction,
)


def run_live_prediction(
    *,
    model_dir: str | Path | None = None,
    window_end: datetime | None = None,
    source: str = "live_api",
) -> dict[str, Any]:
    directory = Path(model_dir or current_app.config["ML_MODEL_DIR"])
    require_model(directory)
    sensor_window = aggregate_sensor_window(window_end)
    record, quality = extract_and_validate_payload(sensor_window)
    prediction = predict_record(directory, record)
    prediction["input_quality"] = quality
    prediction["dry_run_only"] = True
    recommendation = build_dry_run_recommendation_from_prediction(
        directory, record, prediction
    )
    recommendation["input_quality"] = quality

    if current_app.config.get("ML_RECOMMENDATION_LOG_ENABLED", True):
        append_recommendation_log(directory, record, recommendation)

    return upsert_ml_prediction(
        sensor_window=sensor_window,
        prediction=prediction,
        recommendation=recommendation,
        source=source,
    )


def latest_live_prediction() -> dict[str, Any] | None:
    return get_latest_ml_prediction()


def live_prediction_history(limit: int = 50) -> list[dict[str, Any]]:
    return get_ml_predictions(limit)
