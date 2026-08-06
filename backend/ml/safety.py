from __future__ import annotations

from collections.abc import Mapping

from .config import TrainingConfig, VENTILATION_LEVELS


def apply_safety_rules(
    prediction: Mapping[str, object],
    sensor_record: Mapping[str, object],
    config: TrainingConfig,
) -> dict:
    warnings: list[str] = []
    recommended_actions: list[str] = []

    predicted_ventilation = str(prediction["predicted_ventilation"]).upper()
    predicted_occupancy = int(prediction["predicted_occupancy"])
    confidence = float(prediction["occupancy_confidence"])
    empty_probability = float(prediction["empty_probability"])
    empty_safety_validated = bool(prediction.get("empty_safety_validated", False))
    co2 = _number(sensor_record.get("co2_mean_ppm"), 0.0)
    co2_rate = _number(sensor_record.get("co2_rate_ppm_per_min"), 0.0)

    minimum = _normalise_level(
        sensor_record.get("minimum_ventilation", config.minimum_ventilation)
    )
    maximum = _normalise_level(
        sensor_record.get("maximum_ventilation", config.maximum_ventilation)
    )
    if _level_index(minimum) > _level_index(maximum):
        warnings.append("INVALID_VENTILATION_BOUNDS")
        minimum, maximum = config.minimum_ventilation, config.maximum_ventilation

    manual = sensor_record.get("manual_override_ventilation")
    if manual is not None:
        predicted_ventilation = _normalise_level(manual)
        warnings.append("MANUAL_OVERRIDE_APPLIED")

    if co2 >= config.co2_safety_override_ppm:
        predicted_ventilation = "HIGH"
        warnings.append("CO2_SAFETY_OVERRIDE")

    predicted_ventilation = clamp_ventilation(predicted_ventilation, minimum, maximum)

    sensors_unavailable = _all_primary_sensors_unavailable(sensor_record)
    automatic_actions_allowed = True
    if sensors_unavailable:
        warnings.append("SENSOR_DATA_UNAVAILABLE")
        automatic_actions_allowed = False
    if confidence < config.minimum_confidence:
        warnings.append("REQUEST_HUMAN_REVIEW")
        automatic_actions_allowed = False
    if not empty_safety_validated:
        warnings.append("EMPTY_MODEL_BELOW_SAFETY_TARGET")

    if automatic_actions_allowed:
        recommended_actions.append(f"SET_VENTILATION_{predicted_ventilation}")
        overcrowding = bool(prediction.get("overcrowding_risk", False))
        if overcrowding:
            recommended_actions.append("SHOW_CAPACITY_WARNING")

        healthy = not _quality_problem(sensor_record)
        if (
            predicted_occupancy == 0
            and empty_probability >= config.empty_probability_threshold
            and empty_safety_validated
            and co2 < config.co2_energy_saving_max_ppm
            and co2_rate < config.co2_fast_rise_ppm_per_min
            and healthy
        ):
            recommended_actions.extend(
                ["REDUCE_VENTILATION", "ENABLE_ENERGY_SAVING_MODE"]
            )

    return {
        "predicted_ventilation": predicted_ventilation,
        "recommended_actions": _deduplicate(recommended_actions),
        "warnings": _deduplicate(warnings),
        "automatic_actions_allowed": automatic_actions_allowed,
        "dry_run": True,
    }


def clamp_ventilation(level: str, minimum: str, maximum: str) -> str:
    index = _level_index(_normalise_level(level))
    low = _level_index(_normalise_level(minimum))
    high = _level_index(_normalise_level(maximum))
    return VENTILATION_LEVELS[min(max(index, low), high)]


def _all_primary_sensors_unavailable(record: Mapping[str, object]) -> bool:
    pir_unavailable = _flag(record.get("pir_stale_flag")) or all(
        record.get(name) is None
        for name in ("pir_entry_count", "pir_exit_count", "pir_cumulative_estimate")
    )
    radar_unavailable = _flag(record.get("radar_stale_flag")) or _ratio_is_missing(
        record.get("radar_missing_ratio")
    )
    co2_unavailable = _flag(record.get("co2_stale_flag")) or _ratio_is_missing(
        record.get("co2_missing_ratio")
    )
    return pir_unavailable and radar_unavailable and co2_unavailable


def _quality_problem(record: Mapping[str, object]) -> bool:
    if _flag(record.get("radar_stale_flag")) or _flag(record.get("co2_stale_flag")):
        return True
    co2_quality = str(record.get("co2_quality_flag", "GOOD")).upper()
    return co2_quality not in {"GOOD", "OK", "VALID", "0"}


def _ratio_is_missing(value: object) -> bool:
    return _number(value, 1.0) >= 1.0


def _normalise_level(value: object) -> str:
    level = str(value).upper()
    if level not in VENTILATION_LEVELS:
        raise ValueError(
            "Ventilation level must be one of: " + ", ".join(VENTILATION_LEVELS)
        )
    return level


def _level_index(level: str) -> int:
    return VENTILATION_LEVELS.index(level)


def _flag(value: object) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "stale"}
    return bool(value)


def _number(value: object, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _deduplicate(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))
