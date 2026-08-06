from __future__ import annotations

import math
from datetime import datetime

from .config import FEATURE_NAMES, GROUND_TRUTH_COLUMNS, VENTILATION_LEVELS


class RequestValidationError(ValueError):
    def __init__(self, message: str, details: dict | None = None) -> None:
        super().__init__(message)
        self.details = details or {}


RANGE_RULES: dict[str, tuple[float | None, float | None]] = {
    "day_of_week_num": (0, 6),
    "is_weekend": (0, 1),
    "hour": (0, 23),
    "minute": (0, 59),
    "minutes_since_open": (0, 1440),
    "time_sin": (-1, 1),
    "time_cos": (-1, 1),
    "pir_entry_count": (0, None),
    "pir_exit_count": (0, None),
    "pir_event_count": (0, None),
    "pir_entry_event_count": (0, None),
    "pir_exit_event_count": (0, None),
    "pir_total_detected_people": (0, None),
    "pir_max_people_per_event": (0, 3),
    "pir_mean_duration_ms": (0, None),
    "pir_cumulative_estimate": (0, None),
    "radar_presence_ratio": (0, 1),
    "radar_mean_target_count": (0, 3),
    "radar_max_target_count": (0, 3),
    "radar_mean_abs_speed_cm_s": (0, None),
    "radar_mean_distance_mm": (0, None),
    "co2_mean_ppm": (0, None),
    "co2_max_ppm": (0, None),
    "temperature_mean_c": (None, None),
    "humidity_mean_percent": (0, 100),
    "ble_rssi_variance": (0, None),
    "ble_signal_presence_ratio": (0, 1),
    "radar_missing_ratio": (0, 1),
    "co2_missing_ratio": (0, 1),
    "ble_missing_ratio": (0, 1),
}

UNBOUNDED_NUMERIC_FIELDS = {
    "pir_net_count_change",
    "co2_delta_ppm",
    "co2_rate_ppm_per_min",
    "ble_left_rssi_mean_dbm",
    "ble_right_rssi_mean_dbm",
    "ble_left_right_rssi_diff_db",
}

FLAG_FIELDS = {
    "radar_stale_flag",
    "pir_stale_flag",
    "co2_stale_flag",
}

INTEGER_FIELDS = {
    "day_of_week_num",
    "is_weekend",
    "hour",
    "minute",
    "pir_entry_count",
    "pir_exit_count",
    "pir_event_count",
    "pir_entry_event_count",
    "pir_exit_event_count",
    "pir_total_detected_people",
    "pir_max_people_per_event",
    "radar_max_target_count",
}

VENTILATION_FIELDS = {
    "ventilation_current",
    "minimum_ventilation",
    "maximum_ventilation",
    "manual_override_ventilation",
}

BLE_SIDE_VALUES = {"LEFT", "RIGHT", "BALANCED", "NO_SIGNAL"}


def extract_and_validate_payload(payload: object) -> tuple[dict, dict]:
    if not isinstance(payload, dict):
        raise RequestValidationError("Request JSON must be an object")

    top_level_forbidden = sorted(
        key
        for key in payload
        if key.startswith("target_") or key in GROUND_TRUTH_COLUMNS
    )
    if top_level_forbidden:
        raise RequestValidationError(
            "Future targets and ground-truth fields are not accepted by the prediction API",
            {"forbidden_fields": top_level_forbidden},
        )

    record = payload.get("sensor_window", payload)
    if not isinstance(record, dict):
        raise RequestValidationError("sensor_window must be a JSON object")
    validated = dict(record)

    forbidden = sorted(
        key
        for key in validated
        if key.startswith("target_") or key in GROUND_TRUTH_COLUMNS
    )
    if forbidden:
        raise RequestValidationError(
            "Future targets and ground-truth fields are not accepted by the prediction API",
            {"forbidden_fields": forbidden},
        )

    _validate_numeric_fields(validated)
    _validate_flags(validated)
    _validate_categories(validated)
    _validate_timestamps(validated)

    missing = [name for name in FEATURE_NAMES if validated.get(name) is None]
    warnings: list[str] = []
    if missing:
        warnings.append("MISSING_FEATURES_IMPUTED")
    for sensor, field in (
        ("PIR", "pir_stale_flag"),
        ("RADAR", "radar_stale_flag"),
        ("CO2", "co2_stale_flag"),
    ):
        if _truthy(validated.get(field)):
            warnings.append(f"{sensor}_STALE")

    quality = {
        "feature_count_expected": len(FEATURE_NAMES),
        "feature_count_received": len(FEATURE_NAMES) - len(missing),
        "missing_feature_count": len(missing),
        "missing_feature_ratio": round(len(missing) / len(FEATURE_NAMES), 4),
        "missing_features": missing,
        "warnings": warnings,
    }
    return validated, quality


def _validate_numeric_fields(record: dict) -> None:
    for field, (minimum, maximum) in RANGE_RULES.items():
        if field not in record or record[field] is None:
            continue
        value = _number(record[field], field)
        if field in INTEGER_FIELDS and not value.is_integer():
            raise RequestValidationError(f"{field} must be an integer")
        if minimum is not None and value < minimum:
            raise RequestValidationError(f"{field} must be at least {minimum}")
        if maximum is not None and value > maximum:
            raise RequestValidationError(f"{field} must be at most {maximum}")

    for field in UNBOUNDED_NUMERIC_FIELDS:
        if field in record and record[field] is not None:
            _number(record[field], field)


def _validate_flags(record: dict) -> None:
    for field in FLAG_FIELDS:
        if field not in record or record[field] is None:
            continue
        value = record[field]
        if isinstance(value, bool):
            continue
        if isinstance(value, int) and value in (0, 1):
            continue
        if isinstance(value, str) and value.strip().lower() in {
            "0",
            "1",
            "true",
            "false",
            "yes",
            "no",
            "stale",
            "fresh",
        }:
            continue
        raise RequestValidationError(f"{field} must be a boolean or 0/1 flag")


def _validate_categories(record: dict) -> None:
    for field in VENTILATION_FIELDS:
        if field not in record or record[field] is None:
            continue
        if not isinstance(record[field], str):
            raise RequestValidationError(f"{field} must be a string")
        level = record[field].strip().upper()
        if level not in VENTILATION_LEVELS:
            raise RequestValidationError(
                f"{field} must be one of: {', '.join(VENTILATION_LEVELS)}"
            )
        record[field] = level

    side = record.get("ble_dominant_side_estimate")
    if side is not None:
        if not isinstance(side, str) or side.strip().upper() not in BLE_SIDE_VALUES:
            raise RequestValidationError(
                "ble_dominant_side_estimate must be LEFT, RIGHT, BALANCED, or NO_SIGNAL"
            )
        record["ble_dominant_side_estimate"] = side.strip().upper()

    for field in ("co2_quality_flag", "ble_quality_flag"):
        value = record.get(field)
        if value is not None and isinstance(value, (dict, list)):
            raise RequestValidationError(f"{field} must be a scalar value")


def _validate_timestamps(record: dict) -> None:
    parsed: dict[str, datetime] = {}
    for field in ("window_start", "window_end", "prediction_time"):
        value = record.get(field)
        if value is None:
            continue
        if not isinstance(value, str):
            raise RequestValidationError(f"{field} must be an ISO-8601 string")
        try:
            parsed[field] = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise RequestValidationError(
                f"{field} must be a valid ISO-8601 timestamp"
            ) from exc
    if "window_start" in parsed and "window_end" in parsed:
        start_aware = parsed["window_start"].tzinfo is not None
        end_aware = parsed["window_end"].tzinfo is not None
        if start_aware != end_aware:
            raise RequestValidationError(
                "window_start and window_end must use the same timezone style"
            )
        if parsed["window_end"] <= parsed["window_start"]:
            raise RequestValidationError("window_end must be later than window_start")


def _number(value: object, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RequestValidationError(f"{field} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise RequestValidationError(f"{field} must be finite")
    return number


def _truthy(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "stale"}
    return bool(value)
