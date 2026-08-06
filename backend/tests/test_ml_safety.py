from __future__ import annotations

from ml.config import TrainingConfig
from ml.safety import apply_safety_rules


def _prediction(**overrides):
    value = {
        "predicted_ventilation": "LOW",
        "predicted_occupancy": 8,
        "occupancy_confidence": 0.9,
        "empty_probability": 0.0,
        "overcrowding_risk": False,
    }
    value.update(overrides)
    return value


def test_high_co2_forces_high_ventilation():
    result = apply_safety_rules(
        _prediction(),
        {
            "co2_mean_ppm": 1400,
            "pir_entry_count": 1,
            "radar_missing_ratio": 0,
            "co2_missing_ratio": 0,
        },
        TrainingConfig(),
    )

    assert result["predicted_ventilation"] == "HIGH"
    assert "CO2_SAFETY_OVERRIDE" in result["warnings"]


def test_low_confidence_requires_human_review():
    result = apply_safety_rules(
        _prediction(occupancy_confidence=0.59),
        {
            "pir_entry_count": 1,
            "radar_missing_ratio": 0,
            "co2_missing_ratio": 0,
        },
        TrainingConfig(),
    )

    assert not result["automatic_actions_allowed"]
    assert result["recommended_actions"] == []
    assert "REQUEST_HUMAN_REVIEW" in result["warnings"]


def test_all_primary_sensors_stale_blocks_actions():
    result = apply_safety_rules(
        _prediction(),
        {
            "pir_stale_flag": 1,
            "radar_stale_flag": 1,
            "co2_stale_flag": 1,
            "radar_missing_ratio": 1,
            "co2_missing_ratio": 1,
        },
        TrainingConfig(),
    )

    assert not result["automatic_actions_allowed"]
    assert "SENSOR_DATA_UNAVAILABLE" in result["warnings"]


def test_manual_override_and_bounds_are_applied():
    result = apply_safety_rules(
        _prediction(predicted_ventilation="HIGH"),
        {
            "manual_override_ventilation": "MEDIUM",
            "maximum_ventilation": "MEDIUM",
            "pir_entry_count": 1,
            "radar_missing_ratio": 0,
            "co2_missing_ratio": 0,
        },
        TrainingConfig(),
    )

    assert result["predicted_ventilation"] == "MEDIUM"
    assert "MANUAL_OVERRIDE_APPLIED" in result["warnings"]


def test_unvalidated_empty_model_cannot_recommend_energy_saving():
    result = apply_safety_rules(
        _prediction(
            predicted_occupancy=0,
            empty_probability=0.99,
            empty_safety_validated=False,
        ),
        {
            "co2_mean_ppm": 500,
            "co2_rate_ppm_per_min": 0,
            "co2_quality_flag": 0,
            "pir_entry_count": 0,
            "radar_missing_ratio": 0,
            "co2_missing_ratio": 0,
        },
        TrainingConfig(),
    )

    assert "ENABLE_ENERGY_SAVING_MODE" not in result["recommended_actions"]
    assert "EMPTY_MODEL_BELOW_SAFETY_TARGET" in result["warnings"]
