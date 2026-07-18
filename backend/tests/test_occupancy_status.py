"""
Tests for GET /api/occupancy/status — the unified frontend status endpoint.

Each test uses a function-scoped database to ensure full isolation.
"""

import os
import tempfile

import pytest

from app import create_app


# ---------------------------------------------------------------------------
# Function-scoped fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def status_app():
    db_fd, db_path = tempfile.mkstemp(suffix=".db", prefix="test_status_")
    os.close(db_fd)  # Close the OS handle immediately; SQLite will open its own.
    application = create_app(test_config={"TESTING": True, "DATABASE": db_path})
    yield application
    try:
        os.unlink(db_path)
    except OSError:
        pass


@pytest.fixture()
def sc(status_app):
    """Status client with a fresh app + reset mismatch state before each test."""
    client = status_app.test_client()
    # Reset the module-level mismatch tracker between tests.
    import app.routes as routes_mod
    routes_mod._mismatch_started_at = None
    return client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEVICE = "status-pico-01"

_RADAR_0 = {
    "message_type": "radar",
    "device_id": _DEVICE,
    "uptime_ms": 1000,
    "target_count": 0,
    "targets": [],
}

_RADAR_1 = {
    "message_type": "radar",
    "device_id": _DEVICE,
    "uptime_ms": 2000,
    "target_count": 1,
    "targets": [
        {"target_id": 1, "x_mm": 420, "y_mm": 1350,
         "distance_mm": 1413.8, "angle_deg": 17.3, "speed_cm_s": -25},
    ],
}

_ENTRY = {
    "device_id": _DEVICE,
    "event_id": 1,
    "event": "entry",
    "count_change": 1,
    "duration_ms": 800,
    "uptime_ms": 16400,
}


def _post_radar(sc, payload=None):
    return sc.post("/api/radar/readings", json=payload or _RADAR_0)


def _post_entry(sc, event_id=1):
    return sc.post("/api/occupancy/events", json={**_ENTRY, "event_id": event_id})


def _post_exit(sc, event_id=2):
    return sc.post("/api/occupancy/events", json={
        "device_id": _DEVICE,
        "event_id": event_id,
        "event": "exit",
        "count_change": -1,
        "duration_ms": 600,
        "uptime_ms": 20000,
    })


def _get_status(sc):
    return sc.get("/api/occupancy/status")


# ---------------------------------------------------------------------------
# Response structure
# ---------------------------------------------------------------------------

def test_status_returns_200(sc):
    assert _get_status(sc).status_code == 200


def test_status_contains_required_fields(sc):
    data = _get_status(sc).get_json()
    for field in (
        "occupancy", "status", "radar_presence",
        "radar_target_count", "last_occupancy_event_at",
        "last_radar_update_at", "mismatch_started_at",
        "co2_ppm", "co2_level", "temperature_c",
        "humidity_percent", "last_environment_update_at",
    ):
        assert field in data, f"Missing field: {field}"


# ---------------------------------------------------------------------------
# confirmed: occupancy 0 + radar 0
# ---------------------------------------------------------------------------

def test_confirmed_when_both_zero(sc):
    # No occupancy events, no radar data → both agree on "empty"
    data = _get_status(sc).get_json()
    assert data["status"] == "confirmed"
    assert data["occupancy"] == 0
    assert data["radar_target_count"] == 0
    assert data["mismatch_started_at"] is None


def test_confirmed_when_both_zero_with_radar_post(sc):
    _post_radar(sc, _RADAR_0)  # 0 targets
    data = _get_status(sc).get_json()
    assert data["status"] == "confirmed"


# ---------------------------------------------------------------------------
# confirmed: occupancy >= 1 + radar >= 1
# ---------------------------------------------------------------------------

def test_confirmed_when_both_present(sc):
    _post_entry(sc, event_id=10)
    _post_radar(sc, _RADAR_1)
    data = _get_status(sc).get_json()
    assert data["status"] == "confirmed"
    assert data["occupancy"] >= 1
    assert data["radar_target_count"] >= 1
    assert data["mismatch_started_at"] is None


# ---------------------------------------------------------------------------
# uncertain: occupancy 0 + radar sees targets
# ---------------------------------------------------------------------------

def test_uncertain_when_occupancy_zero_radar_present(sc):
    _post_radar(sc, _RADAR_1)  # radar sees 1 target
    # No occupancy events → occupancy = 0
    data = _get_status(sc).get_json()
    assert data["status"] == "uncertain"
    assert data["occupancy"] == 0
    assert data["radar_target_count"] >= 1


# ---------------------------------------------------------------------------
# uncertain: occupancy >= 1 + radar empty
# ---------------------------------------------------------------------------

def test_uncertain_when_occupancy_present_radar_empty(sc):
    _post_entry(sc, event_id=20)
    _post_radar(sc, _RADAR_0)  # radar sees 0 targets
    data = _get_status(sc).get_json()
    assert data["status"] == "uncertain"
    assert data["occupancy"] >= 1
    assert data["radar_target_count"] == 0


# ---------------------------------------------------------------------------
# Occupancy count never changes due to radar data alone
# ---------------------------------------------------------------------------

def test_occupancy_not_changed_by_radar(sc):
    _post_entry(sc, event_id=30)
    before = _get_status(sc).get_json()["occupancy"]

    # Overwrite radar with 0 targets — occupancy must remain unchanged.
    _post_radar(sc, _RADAR_0)
    after = _get_status(sc).get_json()["occupancy"]

    assert before == after


def test_occupancy_not_changed_when_uncertain(sc):
    _post_entry(sc, event_id=40)
    _post_radar(sc, _RADAR_0)  # mismatch: occupancy=1, radar=0
    data = _get_status(sc).get_json()
    assert data["status"] == "uncertain"
    assert data["occupancy"] == 1  # not zeroed out by radar


# ---------------------------------------------------------------------------
# mismatch_started_at tracking
# ---------------------------------------------------------------------------

def test_mismatch_started_at_set_when_uncertain(sc):
    _post_radar(sc, _RADAR_1)  # radar=1, occupancy=0 → uncertain
    data = _get_status(sc).get_json()
    assert data["mismatch_started_at"] is not None


def test_mismatch_started_at_cleared_when_resolved(sc):
    # Create a mismatch.
    _post_radar(sc, _RADAR_1)
    data = _get_status(sc).get_json()
    assert data["status"] == "uncertain"

    # Resolve: post an entry event so occupancy matches radar.
    _post_entry(sc, event_id=50)
    data2 = _get_status(sc).get_json()
    assert data2["status"] == "confirmed"
    assert data2["mismatch_started_at"] is None


def test_mismatch_started_at_stable_across_calls(sc):
    """mismatch_started_at should be the same timestamp on repeated calls."""
    _post_radar(sc, _RADAR_1)  # uncertain
    first = _get_status(sc).get_json()["mismatch_started_at"]
    second = _get_status(sc).get_json()["mismatch_started_at"]
    assert first == second


# ---------------------------------------------------------------------------
# CO2 / environment fields in status response
# ---------------------------------------------------------------------------

_ENV_NORMAL = {
    "message_type": "environment",
    "device_id": _DEVICE,
    "uptime_ms": 5000,
    "co2_ppm": 420,
    "temperature_c": 22.0,
    "humidity_percent": 55.0,
}

_ENV_ELEVATED = {
    "message_type": "environment",
    "device_id": _DEVICE,
    "uptime_ms": 6000,
    "co2_ppm": 1000,
    "temperature_c": 23.0,
    "humidity_percent": 60.0,
}

_ENV_HIGH = {
    "message_type": "environment",
    "device_id": _DEVICE,
    "uptime_ms": 7000,
    "co2_ppm": 2000,
    "temperature_c": 24.0,
    "humidity_percent": 70.0,
}


def _post_env(sc, payload=None):
    return sc.post("/api/co2/readings", json=payload or _ENV_NORMAL)


def test_status_co2_fields_null_when_no_environment_data(sc):
    data = _get_status(sc).get_json()
    assert data["co2_ppm"] is None
    assert data["co2_level"] is None
    assert data["temperature_c"] is None
    assert data["humidity_percent"] is None
    assert data["last_environment_update_at"] is None


def test_status_co2_normal_level(sc):
    _post_env(sc, _ENV_NORMAL)
    data = _get_status(sc).get_json()
    assert data["co2_ppm"] == 420
    assert data["co2_level"] == "normal"
    assert data["temperature_c"] == 22.0
    assert data["humidity_percent"] == 55.0
    assert data["last_environment_update_at"] is not None


def test_status_co2_elevated_level(sc):
    _post_env(sc, _ENV_ELEVATED)
    data = _get_status(sc).get_json()
    assert data["co2_ppm"] == 1000
    assert data["co2_level"] == "elevated"


def test_status_co2_high_level(sc):
    _post_env(sc, _ENV_HIGH)
    data = _get_status(sc).get_json()
    assert data["co2_ppm"] == 2000
    assert data["co2_level"] == "high"


def test_status_co2_does_not_affect_occupancy_count(sc):
    _post_env(sc, _ENV_HIGH)  # high CO2 should not change occupancy
    data = _get_status(sc).get_json()
    assert data["occupancy"] == 0


def test_status_co2_does_not_affect_confirmed_uncertain(sc):
    # Both occupancy and radar are 0 → confirmed, regardless of CO2
    _post_env(sc, _ENV_HIGH)
    data = _get_status(sc).get_json()
    assert data["status"] == "confirmed"
