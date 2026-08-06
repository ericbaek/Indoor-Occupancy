from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request

from .api_service import (
    ModelUnavailableError,
    model_status,
    read_json_artifact,
    read_recommendation_history,
    require_model,
)
from .api_validation import RequestValidationError, extract_and_validate_payload
from .config import FEATURE_NAMES
from .live_scheduler import scheduler_status
from .live_service import (
    latest_live_prediction,
    live_prediction_history,
    run_live_prediction,
)
from .predict import predict_record
from .sensor_aggregation import aggregate_sensor_window, parse_window_end
from .trigger_service import append_recommendation_log, build_dry_run_recommendation


ml_api = Blueprint("ml_api", __name__, url_prefix="/api/ml")


@ml_api.get("/health")
def ml_health():
    status = model_status(_model_dir())
    status["endpoints"] = {
        "predict": "/api/ml/predict",
        "dry_run_recommendation": "/api/ml/recommendations/dry-run",
        "metadata": "/api/ml/metadata",
        "metrics": "/api/ml/metrics",
        "recommendation_history": "/api/ml/recommendations/history",
        "live_predict": "/api/ml/predict/live",
        "latest_live_prediction": "/api/ml/predictions/latest",
        "live_prediction_history": "/api/ml/predictions",
        "latest_sensor_window": "/api/ml/sensor-window/latest",
        "live_status": "/api/ml/live/status",
    }
    return jsonify(status), 200 if status["model_ready"] else 503


@ml_api.get("/metadata")
def ml_metadata():
    try:
        metadata = read_json_artifact(_model_dir(), "metadata.json")
    except ModelUnavailableError as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    return jsonify(
        {
            "metadata": metadata,
            "feature_contract": {
                "features": list(FEATURE_NAMES),
                "missing_values": "accepted_and_imputed",
                "future_targets_accepted": False,
                "ground_truth_accepted": False,
            },
            "dry_run_only": True,
        }
    ), 200


@ml_api.get("/metrics")
def ml_metrics():
    try:
        metrics = read_json_artifact(_model_dir(), "metrics.json")
    except ModelUnavailableError as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    return jsonify(metrics), 200


@ml_api.post("/predict")
def ml_predict():
    try:
        record, quality = _request_record()
        require_model(_model_dir())
        result = predict_record(_model_dir(), record)
    except RequestValidationError as exc:
        return _error("INVALID_SENSOR_WINDOW", str(exc), 400, exc.details)
    except ModelUnavailableError as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    except ValueError as exc:
        return _error("INVALID_SENSOR_WINDOW", str(exc), 400)
    except Exception:
        current_app.logger.exception("ML prediction failed")
        return _error("PREDICTION_FAILED", "ML prediction failed", 500)
    result["input_quality"] = quality
    result["dry_run_only"] = True
    return jsonify(result), 200


@ml_api.post("/recommendations/dry-run")
def ml_dry_run_recommendation():
    try:
        record, quality = _request_record()
        require_model(_model_dir())
        result = build_dry_run_recommendation(_model_dir(), record)
        if current_app.config.get("ML_RECOMMENDATION_LOG_ENABLED", True):
            append_recommendation_log(_model_dir(), record, result)
    except RequestValidationError as exc:
        return _error("INVALID_SENSOR_WINDOW", str(exc), 400, exc.details)
    except ModelUnavailableError as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    except (FileNotFoundError, ModuleNotFoundError) as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    except ValueError as exc:
        return _error("INVALID_SENSOR_WINDOW", str(exc), 400)
    except OSError:
        current_app.logger.exception("ML recommendation log failed")
        return _error("AUDIT_LOG_FAILED", "Recommendation audit log could not be written", 500)
    except Exception:
        current_app.logger.exception("ML recommendation failed")
        return _error("RECOMMENDATION_FAILED", "ML recommendation failed", 500)
    result["input_quality"] = quality
    return jsonify(result), 200


@ml_api.get("/recommendations/history")
def ml_recommendation_history():
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return _error("INVALID_LIMIT", "limit must be an integer", 400)
    if not 1 <= limit <= 200:
        return _error("INVALID_LIMIT", "limit must be between 1 and 200", 400)
    try:
        history = read_recommendation_history(_model_dir(), limit)
    except ModelUnavailableError as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    return jsonify({"recommendations": history, "count": len(history)}), 200


@ml_api.post("/predict/live")
def ml_predict_live():
    try:
        window_end = _optional_window_end() or datetime.now(timezone.utc)
        result = run_live_prediction(
            model_dir=_model_dir(),
            window_end=window_end,
            source="live_api",
        )
    except RequestValidationError as exc:
        return _error("INVALID_SENSOR_WINDOW", str(exc), 400, exc.details)
    except ModelUnavailableError as exc:
        return _error("MODEL_UNAVAILABLE", str(exc), 503)
    except ValueError as exc:
        return _error("INVALID_LIVE_REQUEST", str(exc), 400)
    except OSError:
        current_app.logger.exception("Live ML audit log failed")
        return _error("AUDIT_LOG_FAILED", "Live prediction audit log failed", 500)
    except Exception:
        current_app.logger.exception("Live ML prediction failed")
        return _error("LIVE_PREDICTION_FAILED", "Live prediction failed", 500)
    return jsonify(result), 200


@ml_api.get("/predictions/latest")
def ml_latest_prediction():
    result = latest_live_prediction()
    if result is None:
        return _error(
            "NO_LIVE_PREDICTION",
            "No live prediction has been generated yet",
            404,
        )
    return jsonify(result), 200


@ml_api.get("/predictions")
def ml_prediction_history():
    try:
        limit = int(request.args.get("limit", "50"))
    except ValueError:
        return _error("INVALID_LIMIT", "limit must be an integer", 400)
    if not 1 <= limit <= 200:
        return _error("INVALID_LIMIT", "limit must be between 1 and 200", 400)
    predictions = live_prediction_history(limit)
    return jsonify({"predictions": predictions, "count": len(predictions)}), 200


@ml_api.get("/sensor-window/latest")
def ml_latest_sensor_window():
    try:
        sensor_window = aggregate_sensor_window(datetime.now(timezone.utc))
        _, quality = extract_and_validate_payload(sensor_window)
    except Exception:
        current_app.logger.exception("Sensor window aggregation failed")
        return _error("AGGREGATION_FAILED", "Sensor window aggregation failed", 500)
    return jsonify({"sensor_window": sensor_window, "input_quality": quality}), 200


@ml_api.get("/live/status")
def ml_live_status():
    status = scheduler_status(current_app._get_current_object())
    status["sensor_window_seconds"] = int(
        current_app.config["ML_SENSOR_WINDOW_SECONDS"]
    )
    latest = latest_live_prediction()
    status["latest_prediction"] = (
        {
            "id": latest["id"],
            "window_end": latest["window_end"],
            "forecast_time": latest["forecast_time"],
            "created_at": latest["created_at"],
        }
        if latest is not None
        else None
    )
    return jsonify(status), 200


def _request_record():
    if not request.is_json:
        raise RequestValidationError("Request body must be JSON")
    payload = request.get_json(silent=True)
    if payload is None:
        raise RequestValidationError("Invalid or empty JSON body")
    return extract_and_validate_payload(payload)


def _optional_window_end() -> datetime | None:
    if not request.data:
        return None
    if not request.is_json:
        raise ValueError("Request body must be JSON when supplied")
    payload = request.get_json(silent=True)
    if payload is None:
        raise ValueError("Invalid JSON body")
    if not isinstance(payload, dict):
        raise ValueError("Request JSON must be an object")
    if "window_end" not in payload:
        return None
    parsed = parse_window_end(payload["window_end"])
    if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc):
        raise ValueError("window_end cannot be in the future")
    return parsed


def _model_dir() -> Path:
    return Path(current_app.config["ML_MODEL_DIR"])


def _error(code: str, message: str, status: int, details: dict | None = None):
    payload = {"error": message, "code": code}
    if details:
        payload["details"] = details
    return jsonify(payload), status
