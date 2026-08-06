from __future__ import annotations

from ml import trigger_service
from ml.config import TrainingConfig


def test_trigger_output_is_always_dry_run(monkeypatch):
    monkeypatch.setattr(
        trigger_service,
        "predict_record",
        lambda model_dir, record: {
            "prediction_time": "2026-08-10T12:30:00+10:00",
            "forecast_time": "2026-08-10T13:00:00+10:00",
            "predicted_occupancy": 7,
            "prediction_interval": {"lower": 4, "upper": 10},
            "confidence": 0.9,
            "predicted_ventilation": "LOW",
            "overcrowding": {"overcrowding_risk": False, "risk_probability": 0.1},
            "empty_room": {
                "empty_probability": 0.02,
                "predicted_empty_duration_minutes": 0,
                "safety_validated": False,
            },
            "ble_activity_side": "LEFT",
            "model_version": "1.0.0",
        },
    )
    monkeypatch.setattr(
        trigger_service,
        "load_bundle",
        lambda model_dir: {"config": TrainingConfig().to_dict()},
    )

    result = trigger_service.build_dry_run_recommendation(
        "unused",
        {
            "co2_mean_ppm": 700,
            "pir_entry_count": 1,
            "radar_missing_ratio": 0,
            "co2_missing_ratio": 0,
        },
    )

    assert result["dry_run"] is True
    assert result["hardware_commands_sent"] is False
