from __future__ import annotations

import json

import joblib
import pytest

from app import create_app
from ml import routes as ml_routes
from ml.predict import clear_bundle_cache


@pytest.fixture()
def ml_model_dir(tmp_path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    joblib.dump(
        {
            "model_version": "test-1.0",
            "config": {},
            "feature_names": [],
            "occupancy": {"name": "test_model"},
            "ventilation": {},
            "overcrowding": {},
            "empty_30m": {},
            "empty_60m": {},
        },
        model_dir / "model_bundle.joblib",
    )
    (model_dir / "metadata.json").write_text(
        json.dumps(
            {
                "model_name": "test_model",
                "model_version": "test-1.0",
                "trained_at": "2026-08-06T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (model_dir / "metrics.json").write_text(
        json.dumps({"occupancy": {"selected_model": "test_model"}}),
        encoding="utf-8",
    )
    clear_bundle_cache()
    return model_dir


@pytest.fixture()
def ml_app(tmp_path, ml_model_dir):
    return create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "ml-api.db",
            "ML_MODEL_DIR": str(ml_model_dir),
            "ML_RECOMMENDATION_LOG_ENABLED": True,
        }
    )


@pytest.fixture()
def ml_client(ml_app):
    return ml_app.test_client()


def _prediction_result():
    return {
        "prediction_time": "2026-08-10T12:30:00+10:00",
        "forecast_time": "2026-08-10T13:00:00+10:00",
        "predicted_occupancy": 12,
        "prediction_interval": {"lower": 8, "upper": 16},
        "confidence": 0.8,
        "predicted_ventilation": "LOW",
        "overcrowding": {
            "overcrowding_risk": False,
            "risk_probability": 0.1,
        },
        "empty_room": {"empty_probability": 0.05},
        "ble_activity_side": "LEFT",
        "model_version": "test-1.0",
    }


def _recommendation_result():
    return {
        "prediction_time": "2026-08-10T12:30:00+10:00",
        "forecast_time": "2026-08-10T13:00:00+10:00",
        "predicted_occupancy": 12,
        "predicted_ventilation": "LOW",
        "recommended_actions": ["SET_VENTILATION_LOW"],
        "warnings": [],
        "dry_run": True,
        "hardware_commands_sent": False,
    }


def test_ml_health_reports_ready_model(ml_client):
    response = ml_client.get("/api/ml/health")

    assert response.status_code == 200
    assert response.get_json()["model_ready"] is True
    assert response.get_json()["dry_run_only"] is True


def test_ml_health_reports_missing_model(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "missing.db",
            "ML_MODEL_DIR": str(tmp_path / "missing-model"),
        }
    )

    response = app.test_client().get("/api/ml/health")

    assert response.status_code == 503
    assert response.get_json()["status"] == "model_unavailable"


def test_ml_health_rejects_incomplete_bundle(tmp_path):
    model_dir = tmp_path / "invalid-model"
    model_dir.mkdir()
    joblib.dump({"occupancy": {}}, model_dir / "model_bundle.joblib")
    clear_bundle_cache()
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": tmp_path / "invalid.db",
            "ML_MODEL_DIR": str(model_dir),
        }
    )

    response = app.test_client().get("/api/ml/health")

    assert response.status_code == 503
    assert "missing section" in response.get_json()["reason"]


def test_ml_metadata_and_metrics(ml_client):
    metadata = ml_client.get("/api/ml/metadata")
    metrics = ml_client.get("/api/ml/metrics")

    assert metadata.status_code == 200
    assert metadata.get_json()["metadata"]["model_name"] == "test_model"
    assert metadata.get_json()["feature_contract"]["future_targets_accepted"] is False
    assert metrics.status_code == 200
    assert metrics.get_json()["occupancy"]["selected_model"] == "test_model"


def test_ml_predict_accepts_flat_sensor_window(ml_client, monkeypatch):
    monkeypatch.setattr(
        ml_routes,
        "predict_record",
        lambda model_dir, record: _prediction_result(),
    )

    response = ml_client.post(
        "/api/ml/predict",
        json={
            "window_end": "2026-08-10T12:30:00+10:00",
            "hour": 12,
            "minute": 30,
            "pir_max_people_per_event": 3,
            "radar_max_target_count": 2,
        },
    )

    body = response.get_json()
    assert response.status_code == 200
    assert body["predicted_occupancy"] == 12
    assert body["input_quality"]["missing_feature_count"] > 0
    assert "MISSING_FEATURES_IMPUTED" in body["input_quality"]["warnings"]
    assert body["dry_run_only"] is True


@pytest.mark.parametrize(
    "payload",
    [
        {"target_occupancy_plus_30m": 20},
        {"ground_truth_occupancy": 20},
        {"pir_max_people_per_event": 4},
        {"pir_entry_count": 1.5},
        {"radar_max_target_count": 4},
        {"humidity_mean_percent": 101},
        {"window_end": "not-a-time"},
        {"ventilation_current": "TURBO"},
        {
            "window_start": "2026-08-10T12:25:00",
            "window_end": "2026-08-10T12:30:00+10:00",
        },
        {
            "sensor_window": {"hour": 12},
            "target_occupancy_plus_30m": 20,
        },
    ],
)
def test_ml_predict_rejects_unsafe_or_invalid_fields(ml_client, payload):
    response = ml_client.post("/api/ml/predict", json=payload)

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_SENSOR_WINDOW"


def test_ml_predict_requires_json(ml_client):
    response = ml_client.post("/api/ml/predict", data="hour=12")

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_SENSOR_WINDOW"


def test_dry_run_recommendation_is_logged_and_queryable(
    ml_client,
    monkeypatch,
):
    monkeypatch.setattr(
        ml_routes,
        "build_dry_run_recommendation",
        lambda model_dir, record: _recommendation_result(),
    )

    response = ml_client.post(
        "/api/ml/recommendations/dry-run",
        json={"sensor_window": {"hour": 12, "minute": 30}},
    )
    history = ml_client.get("/api/ml/recommendations/history?limit=1")

    assert response.status_code == 200
    assert response.get_json()["dry_run"] is True
    assert response.get_json()["hardware_commands_sent"] is False
    assert history.status_code == 200
    assert history.get_json()["count"] == 1
    assert history.get_json()["recommendations"][0]["dry_run"] is True


@pytest.mark.parametrize("limit", ["zero", "0", "201"])
def test_recommendation_history_rejects_invalid_limit(ml_client, limit):
    response = ml_client.get(f"/api/ml/recommendations/history?limit={limit}")

    assert response.status_code == 400
    assert response.get_json()["code"] == "INVALID_LIMIT"
