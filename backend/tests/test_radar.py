"""
Tests for radar endpoints:
  POST /api/radar/readings
  GET  /api/radar/latest
  GET  /api/radar/latest/<device_id>

Each test uses a function-scoped database so tests are fully isolated.
"""

import os
import tempfile

import pytest

from app import create_app


# ---------------------------------------------------------------------------
# Function-scoped fixtures for full test isolation
# ---------------------------------------------------------------------------

@pytest.fixture()
def radar_app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_radar_")
    os.close(db_fd)  # Close the OS handle immediately; SQLite will open its own.
    application = create_app(test_config={"TESTING": True, "DATABASE": db_path})
    yield application
    # Windows may keep a brief lock on the file after SQLite closes it.
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture()
def rc(radar_app):
    return radar_app.test_client()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEVICE = "doorway-pico-01"

_VALID_RADAR_0 = {
    "message_type": "radar",
    "device_id": _DEVICE,
    "uptime_ms": 1000,
    "target_count": 0,
    "targets": [],
}

_TARGET_1 = {
    "target_id": 1,
    "x_mm": 420,
    "y_mm": 1350,
    "distance_mm": 1413.8,
    "angle_deg": 17.3,
    "speed_cm_s": -25,
}

_VALID_RADAR_1 = {
    "message_type": "radar",
    "device_id": _DEVICE,
    "uptime_ms": 2000,
    "target_count": 1,
    "targets": [_TARGET_1],
}

_VALID_RADAR_3 = {
    "message_type": "radar",
    "device_id": _DEVICE,
    "uptime_ms": 3000,
    "target_count": 3,
    "targets": [
        {"target_id": 1, "x_mm": 100, "y_mm": 500,
         "distance_mm": 510.0, "angle_deg": 11.3, "speed_cm_s": 0},
        {"target_id": 2, "x_mm": -200, "y_mm": 800,
         "distance_mm": 824.6, "angle_deg": -14.0, "speed_cm_s": 5},
        {"target_id": 3, "x_mm": 50, "y_mm": 1200,
         "distance_mm": 1201.0, "angle_deg": 2.4, "speed_cm_s": -10},
    ],
}


def _post(client, payload):
    return client.post("/api/radar/readings", json=payload)


# ---------------------------------------------------------------------------
# Valid payloads
# ---------------------------------------------------------------------------

def test_radar_0_targets_returns_201(rc):
    assert _post(rc, _VALID_RADAR_0).status_code == 201


def test_radar_1_target_returns_201(rc):
    assert _post(rc, _VALID_RADAR_1).status_code == 201


def test_radar_3_targets_returns_201(rc):
    assert _post(rc, _VALID_RADAR_3).status_code == 201


def test_radar_success_body(rc):
    data = _post(rc, _VALID_RADAR_1).get_json()
    assert data["success"] is True
    assert data["data"]["device_id"] == _DEVICE
    assert data["data"]["target_count"] == 1


# ---------------------------------------------------------------------------
# target_count validation
# ---------------------------------------------------------------------------

def test_radar_target_count_4_returns_400(rc):
    payload = {**_VALID_RADAR_0, "target_count": 4}
    assert _post(rc, payload).status_code == 400


def test_radar_target_count_negative_returns_400(rc):
    payload = {**_VALID_RADAR_0, "target_count": -1}
    assert _post(rc, payload).status_code == 400


def test_radar_target_count_mismatch_returns_400(rc):
    # target_count says 2 but targets array has 1 item.
    payload = {**_VALID_RADAR_1, "target_count": 2}
    assert _post(rc, payload).status_code == 400


def test_radar_target_count_mismatch_error_message(rc):
    payload = {**_VALID_RADAR_1, "target_count": 2}
    data = _post(rc, payload).get_json()
    assert "target_count" in data["error"]


# ---------------------------------------------------------------------------
# Target field validation
# ---------------------------------------------------------------------------

def test_radar_missing_target_field_returns_400(rc):
    incomplete_target = {"target_id": 1, "x_mm": 100}  # missing y_mm, etc.
    payload = {
        "message_type": "radar",
        "device_id": _DEVICE,
        "uptime_ms": 1000,
        "target_count": 1,
        "targets": [incomplete_target],
    }
    assert _post(rc, payload).status_code == 400


def test_radar_missing_target_field_error_message(rc):
    incomplete_target = {"target_id": 1, "x_mm": 100}
    payload = {
        "message_type": "radar",
        "device_id": _DEVICE,
        "uptime_ms": 1000,
        "target_count": 1,
        "targets": [incomplete_target],
    }
    data = _post(rc, payload).get_json()
    assert "error" in data


def test_radar_bool_as_numeric_field_returns_400(rc):
    bad_target = {**_TARGET_1, "x_mm": True}  # bool is not a valid number here
    payload = {
        "message_type": "radar",
        "device_id": _DEVICE,
        "uptime_ms": 1000,
        "target_count": 1,
        "targets": [bad_target],
    }
    assert _post(rc, payload).status_code == 400


def test_radar_string_as_numeric_field_returns_400(rc):
    bad_target = {**_TARGET_1, "distance_mm": "far"}
    payload = {
        "message_type": "radar",
        "device_id": _DEVICE,
        "uptime_ms": 1000,
        "target_count": 1,
        "targets": [bad_target],
    }
    assert _post(rc, payload).status_code == 400


# ---------------------------------------------------------------------------
# message_type validation
# ---------------------------------------------------------------------------

def test_radar_wrong_message_type_returns_400(rc):
    payload = {**_VALID_RADAR_0, "message_type": "occupancy_event"}
    assert _post(rc, payload).status_code == 400


def test_radar_missing_message_type_returns_400(rc):
    payload = {k: v for k, v in _VALID_RADAR_0.items() if k != "message_type"}
    assert _post(rc, payload).status_code == 400


# ---------------------------------------------------------------------------
# device_id validation
# ---------------------------------------------------------------------------

def test_radar_empty_device_id_returns_400(rc):
    payload = {**_VALID_RADAR_0, "device_id": "   "}
    assert _post(rc, payload).status_code == 400


# ---------------------------------------------------------------------------
# GET /api/radar/latest
# ---------------------------------------------------------------------------

def test_get_radar_latest_empty_returns_200(rc):
    resp = rc.get("/api/radar/latest")
    assert resp.status_code == 200
    data = resp.get_json()
    assert "devices" in data


def test_get_radar_latest_after_post(rc):
    _post(rc, _VALID_RADAR_1)
    data = rc.get("/api/radar/latest").get_json()
    assert len(data["devices"]) == 1
    assert data["devices"][0]["device_id"] == _DEVICE
    assert data["devices"][0]["target_count"] == 1
    assert isinstance(data["devices"][0]["targets"], list)


def test_get_radar_latest_contains_required_fields(rc):
    _post(rc, _VALID_RADAR_1)
    device = rc.get("/api/radar/latest").get_json()["devices"][0]
    for field in ("device_id", "uptime_ms", "target_count", "targets", "received_at"):
        assert field in device, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# GET /api/radar/latest/<device_id>
# ---------------------------------------------------------------------------

def test_get_radar_latest_device_returns_200(rc):
    _post(rc, _VALID_RADAR_1)
    assert rc.get(f"/api/radar/latest/{_DEVICE}").status_code == 200


def test_get_radar_latest_device_not_found_returns_404(rc):
    assert rc.get("/api/radar/latest/nonexistent-device-99").status_code == 404


def test_get_radar_latest_device_404_body_contains_error(rc):
    data = rc.get("/api/radar/latest/nonexistent-device-99").get_json()
    assert "error" in data


def test_get_radar_latest_device_data_matches(rc):
    _post(rc, _VALID_RADAR_1)
    data = rc.get(f"/api/radar/latest/{_DEVICE}").get_json()
    assert data["device_id"] == _DEVICE
    assert data["target_count"] == 1
    assert len(data["targets"]) == 1
    assert data["targets"][0]["x_mm"] == _TARGET_1["x_mm"]


# ---------------------------------------------------------------------------
# Latest value is always updated (even with rapid posts)
# ---------------------------------------------------------------------------

def test_radar_latest_is_updated_on_new_reading(rc):
    _post(rc, _VALID_RADAR_1)
    # Post again with 0 targets — latest must reflect the new state.
    _post(rc, {**_VALID_RADAR_0, "uptime_ms": 9999})
    data = rc.get(f"/api/radar/latest/{_DEVICE}").get_json()
    assert data["target_count"] == 0


def test_radar_two_devices_stored_separately(rc):
    _post(rc, _VALID_RADAR_1)
    _post(rc, {**_VALID_RADAR_0, "device_id": "second-pico-02"})
    data = rc.get("/api/radar/latest").get_json()
    device_ids = {d["device_id"] for d in data["devices"]}
    assert _DEVICE in device_ids
    assert "second-pico-02" in device_ids


# ---------------------------------------------------------------------------
# History throttling — radar_readings table
# ---------------------------------------------------------------------------

def test_radar_history_throttle_within_one_second(radar_app, rc):
    """Multiple rapid posts should only create one history record."""
    _post(rc, _VALID_RADAR_0)
    _post(rc, {**_VALID_RADAR_0, "uptime_ms": 1100})
    _post(rc, {**_VALID_RADAR_0, "uptime_ms": 1200})

    with radar_app.app_context():
        from app.database import get_db
        count = get_db().execute(
            "SELECT COUNT(*) AS n FROM radar_readings WHERE device_id = ?",
            (_DEVICE,),
        ).fetchone()["n"]

    assert count == 1, "Expected only 1 history row within one second"
