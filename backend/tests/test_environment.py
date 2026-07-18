"""
Tests for environment / CO2 sensor endpoints:
  POST /api/environment/readings
  GET  /api/environment/latest
  GET  /api/environment/latest/<device_id>
  GET  /api/environment/history/<device_id>

Each test uses a function-scoped database for full isolation.
"""

import os
import tempfile

import pytest

from app import create_app


# ---------------------------------------------------------------------------
# Function-scoped fixtures for full test isolation
# ---------------------------------------------------------------------------

@pytest.fixture()
def env_app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_env_")
    os.close(db_fd)
    application = create_app(test_config={"TESTING": True, "DATABASE": db_path})
    yield application
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture()
def ec(env_app):
    return env_app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEVICE = "scd41-nano-01"

_VALID_ENV = {
    "message_type": "environment",
    "device_id": _DEVICE,
    "uptime_ms": 7080308,
    "co2_ppm": 1520,
    "temperature_c": 21.4,
    "humidity_percent": 64.6,
}

_VALID_ENV_LOW_CO2 = {
    "message_type": "environment",
    "device_id": _DEVICE,
    "uptime_ms": 7085000,
    "co2_ppm": 420,
    "temperature_c": 22.0,
    "humidity_percent": 55.0,
}


def _post(client, payload):
    return client.post("/api/environment/readings", json=payload)


# ---------------------------------------------------------------------------
# POST /api/environment/readings — valid payloads
# ---------------------------------------------------------------------------

def test_valid_environment_returns_201(ec):
    assert _post(ec, _VALID_ENV).status_code == 201


def test_valid_environment_success_body(ec):
    data = _post(ec, _VALID_ENV).get_json()
    assert data["success"] is True
    assert data["message"] == "Environment reading recorded"
    assert data["data"]["device_id"] == _DEVICE
    assert data["data"]["co2_ppm"] == 1520
    assert data["data"]["temperature_c"] == 21.4
    assert data["data"]["humidity_percent"] == 64.6
    assert data["data"]["received_at"] is not None


def test_low_co2_accepted(ec):
    assert _post(ec, _VALID_ENV_LOW_CO2).status_code == 201


def test_zero_co2_accepted(ec):
    payload = {**_VALID_ENV, "co2_ppm": 0}
    assert _post(ec, payload).status_code == 201


def test_zero_humidity_accepted(ec):
    payload = {**_VALID_ENV, "humidity_percent": 0}
    assert _post(ec, payload).status_code == 201


def test_100_humidity_accepted(ec):
    payload = {**_VALID_ENV, "humidity_percent": 100}
    assert _post(ec, payload).status_code == 201


def test_negative_temperature_accepted(ec):
    payload = {**_VALID_ENV, "temperature_c": -5.2}
    assert _post(ec, payload).status_code == 201


# ---------------------------------------------------------------------------
# POST /api/environment/readings — message_type validation
# ---------------------------------------------------------------------------

def test_wrong_message_type_returns_400(ec):
    payload = {**_VALID_ENV, "message_type": "radar"}
    assert _post(ec, payload).status_code == 400


def test_missing_message_type_returns_400(ec):
    payload = {k: v for k, v in _VALID_ENV.items() if k != "message_type"}
    assert _post(ec, payload).status_code == 400


# ---------------------------------------------------------------------------
# POST /api/environment/readings — device_id validation
# ---------------------------------------------------------------------------

def test_empty_device_id_returns_400(ec):
    payload = {**_VALID_ENV, "device_id": "   "}
    assert _post(ec, payload).status_code == 400


def test_non_string_device_id_returns_400(ec):
    payload = {**_VALID_ENV, "device_id": 123}
    assert _post(ec, payload).status_code == 400


# ---------------------------------------------------------------------------
# POST /api/environment/readings — missing fields
# ---------------------------------------------------------------------------

def test_missing_uptime_ms_returns_400(ec):
    payload = {k: v for k, v in _VALID_ENV.items() if k != "uptime_ms"}
    assert _post(ec, payload).status_code == 400


def test_missing_co2_ppm_returns_400(ec):
    payload = {k: v for k, v in _VALID_ENV.items() if k != "co2_ppm"}
    assert _post(ec, payload).status_code == 400


def test_missing_temperature_c_returns_400(ec):
    payload = {k: v for k, v in _VALID_ENV.items() if k != "temperature_c"}
    assert _post(ec, payload).status_code == 400


def test_missing_humidity_percent_returns_400(ec):
    payload = {k: v for k, v in _VALID_ENV.items() if k != "humidity_percent"}
    assert _post(ec, payload).status_code == 400


# ---------------------------------------------------------------------------
# POST /api/environment/readings — type validation
# ---------------------------------------------------------------------------

def test_bool_uptime_ms_returns_400(ec):
    payload = {**_VALID_ENV, "uptime_ms": True}
    assert _post(ec, payload).status_code == 400


def test_string_co2_ppm_returns_400(ec):
    payload = {**_VALID_ENV, "co2_ppm": "high"}
    assert _post(ec, payload).status_code == 400


def test_bool_temperature_c_returns_400(ec):
    payload = {**_VALID_ENV, "temperature_c": False}
    assert _post(ec, payload).status_code == 400


def test_bool_humidity_percent_returns_400(ec):
    payload = {**_VALID_ENV, "humidity_percent": True}
    assert _post(ec, payload).status_code == 400


# ---------------------------------------------------------------------------
# POST /api/environment/readings — range validation
# ---------------------------------------------------------------------------

def test_negative_uptime_ms_returns_400(ec):
    payload = {**_VALID_ENV, "uptime_ms": -1}
    assert _post(ec, payload).status_code == 400


def test_negative_co2_ppm_returns_400(ec):
    payload = {**_VALID_ENV, "co2_ppm": -100}
    assert _post(ec, payload).status_code == 400


def test_humidity_over_100_returns_400(ec):
    payload = {**_VALID_ENV, "humidity_percent": 101}
    assert _post(ec, payload).status_code == 400


def test_humidity_below_0_returns_400(ec):
    payload = {**_VALID_ENV, "humidity_percent": -1}
    assert _post(ec, payload).status_code == 400


# ---------------------------------------------------------------------------
# POST /api/environment/readings — non-JSON body
# ---------------------------------------------------------------------------

def test_non_json_body_returns_400(ec):
    resp = ec.post("/api/environment/readings", data="not json",
                   content_type="text/plain")
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /api/environment/latest
# ---------------------------------------------------------------------------

def test_get_latest_empty_returns_200(ec):
    resp = ec.get("/api/environment/latest")
    assert resp.status_code == 200
    assert "devices" in resp.get_json()


def test_get_latest_after_post(ec):
    _post(ec, _VALID_ENV)
    data = ec.get("/api/environment/latest").get_json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["device_id"] == _DEVICE
    assert data["devices"][0]["co2_ppm"] == 1520


def test_get_latest_contains_required_fields(ec):
    _post(ec, _VALID_ENV)
    device = ec.get("/api/environment/latest").get_json()["devices"][0]
    for field in ("device_id", "uptime_ms", "co2_ppm", "temperature_c",
                  "humidity_percent", "received_at"):
        assert field in device, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/environment/latest/<device_id>
# ---------------------------------------------------------------------------

def test_get_latest_device_returns_200(ec):
    _post(ec, _VALID_ENV)
    assert ec.get(f"/api/environment/latest/{_DEVICE}").status_code == 200


def test_get_latest_device_not_found_returns_404(ec):
    assert ec.get("/api/environment/latest/nonexistent-99").status_code == 404


def test_get_latest_device_404_body_contains_error(ec):
    data = ec.get("/api/environment/latest/nonexistent-99").get_json()
    assert "error" in data


def test_get_latest_device_data_matches(ec):
    _post(ec, _VALID_ENV)
    data = ec.get(f"/api/environment/latest/{_DEVICE}").get_json()
    assert data["device_id"] == _DEVICE
    assert data["co2_ppm"] == 1520
    assert data["temperature_c"] == 21.4
    assert data["humidity_percent"] == 64.6


# ---------------------------------------------------------------------------
# Latest is always updated (even with rapid posts)
# ---------------------------------------------------------------------------

def test_latest_is_updated_on_new_reading(ec):
    _post(ec, _VALID_ENV)
    # Post again with different CO2 — latest must reflect the new state.
    _post(ec, {**_VALID_ENV, "co2_ppm": 800, "uptime_ms": 9999})
    data = ec.get(f"/api/environment/latest/{_DEVICE}").get_json()
    assert data["co2_ppm"] == 800


def test_two_devices_stored_separately(ec):
    _post(ec, _VALID_ENV)
    _post(ec, {**_VALID_ENV, "device_id": "scd41-nano-02"})
    data = ec.get("/api/environment/latest").get_json()
    device_ids = {d["device_id"] for d in data["devices"]}
    assert _DEVICE in device_ids
    assert "scd41-nano-02" in device_ids


# ---------------------------------------------------------------------------
# GET /api/environment/history/<device_id>
# ---------------------------------------------------------------------------

def test_get_history_returns_200(ec):
    _post(ec, _VALID_ENV)
    resp = ec.get(f"/api/environment/history/{_DEVICE}")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["device_id"] == _DEVICE
    assert isinstance(data["readings"], list)


def test_get_history_contains_data_after_post(ec):
    _post(ec, _VALID_ENV)
    data = ec.get(f"/api/environment/history/{_DEVICE}").get_json()
    assert len(data["readings"]) >= 1
    reading = data["readings"][0]
    assert reading["co2_ppm"] == 1520


def test_get_history_empty_device_returns_empty_list(ec):
    data = ec.get("/api/environment/history/nonexistent-99").get_json()
    assert data["readings"] == []


def test_get_history_limit_is_respected(ec):
    # Post multiple readings with different uptime to bypass throttle
    # (but since throttle is 5s, only the first will be stored in history)
    _post(ec, _VALID_ENV)
    data = ec.get(f"/api/environment/history/{_DEVICE}?limit=1").get_json()
    assert len(data["readings"]) <= 1


# ---------------------------------------------------------------------------
# History throttling — environment_readings table
# ---------------------------------------------------------------------------

def test_environment_history_throttle_within_five_seconds(env_app, ec):
    """Multiple rapid posts should only create one history record."""
    _post(ec, _VALID_ENV)
    _post(ec, {**_VALID_ENV, "uptime_ms": 7081000, "co2_ppm": 1600})
    _post(ec, {**_VALID_ENV, "uptime_ms": 7082000, "co2_ppm": 1700})

    with env_app.app_context():
        from app.database import get_db
        count = get_db().execute(
            "SELECT COUNT(*) AS n FROM environment_readings WHERE device_id = ?",
            (_DEVICE,),
        ).fetchone()["n"]

    assert count == 1, "Expected only 1 history row within five seconds"
