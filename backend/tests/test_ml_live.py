from __future__ import annotations

import json
from datetime import datetime, timezone

import joblib
import pytest

from app import create_app
from app.database import get_db
from ml import live_service
from ml.predict import clear_bundle_cache
from ml.sensor_aggregation import aggregate_sensor_window


@pytest.fixture()
def live_model_dir(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    joblib.dump(
        {
            "model_version": "live-test-1.0",
            "config": {},
            "feature_names": [],
            "occupancy": {"name": "test"},
            "ventilation": {},
            "overcrowding": {},
            "empty_30m": {},
            "empty_60m": {},
        },
        model_dir / "model_bundle.joblib",
    )
    clear_bundle_cache()
    return model_dir


@pytest.fixture()
def live_app(tmp_path, live_model_dir):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "live.db",
            "ML_MODEL_DIR": str(live_model_dir),
            "ML_RECOMMENDATION_LOG_ENABLED": False,
            "ML_LIVE_PREDICTION_ENABLED": True,
        }
    )


def _insert_sensor_history(app):
    with app.app_context():
        db = get_db()
        db.executemany(
            """
            INSERT INTO occupancy_events
                (device_id, event_id, event, count_change, duration_ms,
                 uptime_ms, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            [
                ("pir-1", 1, "entry", 1, 500, 1000, "2026-08-06T02:00:10+00:00"),
                ("pir-1", 2, "entry", 1, 700, 2000, "2026-08-06T02:01:10+00:00"),
                ("pir-1", 3, "exit", -1, 600, 3000, "2026-08-06T02:02:10+00:00"),
            ],
        )
        targets = json.dumps(
            [
                {
                    "target_id": 1,
                    "x_mm": 0,
                    "y_mm": 1000,
                    "distance_mm": 1000,
                    "angle_deg": 0,
                    "speed_cm_s": -10,
                }
            ]
        )
        db.executemany(
            """
            INSERT INTO radar_readings
                (device_id, uptime_ms, target_count, targets_json, received_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                ("radar-1", 1000, 1, targets, "2026-08-06T02:00:20+00:00"),
                ("radar-1", 2000, 0, "[]", "2026-08-06T02:04:59+00:00"),
            ],
        )
        db.execute(
            """
            INSERT INTO radar_latest
                (device_id, uptime_ms, target_count, targets_json, received_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("radar-1", 2000, 0, "[]", "2026-08-06T02:04:59+00:00"),
        )
        db.executemany(
            """
            INSERT INTO environment_readings
                (device_id, uptime_ms, co2_ppm, temperature_c,
                 humidity_percent, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                ("co2-1", 1000, 500, 22.0, 50.0, "2026-08-06T02:00:10+00:00"),
                ("co2-1", 2000, 520, 24.0, 52.0, "2026-08-06T02:04:50+00:00"),
            ],
        )
        db.execute(
            """
            INSERT INTO environment_latest
                (device_id, uptime_ms, co2_ppm, temperature_c,
                 humidity_percent, received_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("co2-1", 2000, 520, 24.0, 52.0, "2026-08-06T02:04:50+00:00"),
        )
        db.executemany(
            """
            INSERT INTO bluetooth_readings
                (scanner_id, tag_id, rssi, received_at)
            VALUES (?, ?, ?, ?)
            """,
            [
                ("anchor-left", "ROOM-TAG-01", -50, "2026-08-06T02:00:30+00:00"),
                ("anchor-left", "ROOM-TAG-01", -52, "2026-08-06T02:01:30+00:00"),
                ("anchor-right", "ROOM-TAG-01", -70, "2026-08-06T02:02:30+00:00"),
                ("anchor-right", "ROOM-TAG-01", -68, "2026-08-06T02:03:30+00:00"),
            ],
        )
        db.commit()


def _prediction_result():
    return {
        "prediction_time": "2026-08-06T12:05:00+10:00",
        "forecast_time": "2026-08-06T12:35:00+10:00",
        "predicted_occupancy": 8,
        "prediction_interval": {"lower": 5, "upper": 11},
        "confidence": 0.8,
        "predicted_ventilation": "LOW",
        "overcrowding": {
            "overcrowding_risk": False,
            "risk_probability": 0.1,
        },
        "empty_room": {
            "empty_probability_30m": 0.1,
            "empty_probability": 0.2,
            "safety_validated": False,
        },
        "ble_activity_side": "LEFT",
        "model_version": "live-test-1.0",
    }


def _recommendation_result():
    return {
        "prediction_time": "2026-08-06T12:05:00+10:00",
        "forecast_time": "2026-08-06T12:35:00+10:00",
        "predicted_occupancy": 8,
        "predicted_ventilation": "LOW",
        "recommended_actions": ["SET_VENTILATION_LOW"],
        "warnings": [],
        "dry_run": True,
        "hardware_commands_sent": False,
    }


def test_sensor_history_is_aggregated_into_model_features(live_app):
    _insert_sensor_history(live_app)

    with live_app.app_context():
        record = aggregate_sensor_window(
            datetime(2026, 8, 6, 2, 5, tzinfo=timezone.utc)
        )

    assert record["window_start"] == "2026-08-06T12:00:00+10:00"
    assert record["window_end"] == "2026-08-06T12:05:00+10:00"
    assert record["minutes_since_open"] == 180
    assert record["pir_entry_count"] == 2
    assert record["pir_exit_count"] == 1
    assert record["pir_net_count_change"] == 1
    assert record["pir_cumulative_estimate"] == 1
    assert record["radar_presence_ratio"] == 0.5
    assert record["radar_mean_target_count"] == 0.5
    assert record["radar_mean_abs_speed_cm_s"] == 10.0
    assert record["radar_mean_distance_mm"] == 1000.0
    assert record["co2_mean_ppm"] == 510.0
    assert record["co2_delta_ppm"] == 20.0
    assert record["temperature_mean_c"] == 23.0
    assert record["ble_left_rssi_mean_dbm"] == -51.0
    assert record["ble_right_rssi_mean_dbm"] == -69.0
    assert record["ble_left_right_rssi_diff_db"] == 18.0
    assert record["ble_dominant_side_estimate"] == "LEFT"
    assert record["aggregation_metadata"]["ble"]["active_tag_count"] == 1


def test_live_prediction_is_saved_and_available_to_frontend(
    live_app,
    monkeypatch,
):
    monkeypatch.setattr(
        live_service, "predict_record", lambda model_dir, record: _prediction_result()
    )
    monkeypatch.setattr(
        live_service,
        "build_dry_run_recommendation_from_prediction",
        lambda model_dir, record, prediction: _recommendation_result(),
    )
    client = live_app.test_client()

    generated = client.post("/api/ml/predict/live")
    latest = client.get("/api/ml/predictions/latest")
    history = client.get("/api/ml/predictions?limit=10")

    assert generated.status_code == 200
    assert generated.get_json()["prediction"]["predicted_occupancy"] == 8
    assert generated.get_json()["recommendation"]["dry_run"] is True
    assert latest.status_code == 200
    assert latest.get_json()["id"] == generated.get_json()["id"]
    assert history.status_code == 200
    assert history.get_json()["count"] == 1


def test_same_live_window_is_upserted_instead_of_duplicated(
    live_app,
    monkeypatch,
):
    monkeypatch.setattr(
        live_service, "predict_record", lambda model_dir, record: _prediction_result()
    )
    monkeypatch.setattr(
        live_service,
        "build_dry_run_recommendation_from_prediction",
        lambda model_dir, record, prediction: _recommendation_result(),
    )
    client = live_app.test_client()
    payload = {"window_end": datetime.now(timezone.utc).isoformat()}

    first = client.post("/api/ml/predict/live", json=payload)
    second = client.post("/api/ml/predict/live", json=payload)
    history = client.get("/api/ml/predictions")

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.get_json()["id"] == second.get_json()["id"]
    assert history.get_json()["count"] == 1


def test_live_status_exposes_scheduler_and_latest_prediction(live_app):
    response = live_app.test_client().get("/api/ml/live/status")

    assert response.status_code == 200
    assert response.get_json()["running"] is False
    assert response.get_json()["interval_seconds"] == 300
    assert response.get_json()["sensor_window_seconds"] == 300
