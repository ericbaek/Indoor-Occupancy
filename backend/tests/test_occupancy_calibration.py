import pytest

from app.database import get_db


@pytest.fixture(autouse=True)
def clear_occupancy_events(app):
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM occupancy_events")
        db.commit()
    yield
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM occupancy_events")
        db.commit()


def test_calibration_sets_exact_occupancy(client):
    response = client.post("/api/occupancy/calibrate", json={"occupancy": 4})

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["previous_occupancy"] == 0
    assert data["occupancy"] == 4
    assert data["count_change"] == 4
    assert data["events_created"] == 4
    assert client.get("/api/occupancy/current").get_json()["occupancy"] == 4


def test_calibration_increases_and_decreases_by_delta(client):
    client.post("/api/occupancy/calibrate", json={"occupancy": 5})

    increased = client.post("/api/occupancy/calibrate", json={"delta": 1})
    assert increased.get_json()["data"]["occupancy"] == 6

    decreased = client.post("/api/occupancy/calibrate", json={"delta": -1})
    assert decreased.get_json()["data"]["occupancy"] == 5
    assert client.get("/api/occupancy/current").get_json()["occupancy"] == 5


def test_calibration_never_decreases_below_zero(client):
    response = client.post("/api/occupancy/calibrate", json={"delta": -1})

    assert response.status_code == 200
    assert response.get_json()["data"]["occupancy"] == 0
    assert client.get("/api/occupancy/current").get_json()["occupancy"] == 0


def test_pir_events_continue_after_calibration(client):
    client.post("/api/occupancy/calibrate", json={"occupancy": 3})
    response = client.post("/api/occupancy/events", json={
        "device_id": "doorway-pico-01",
        "event_id": 1,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 250,
        "uptime_ms": 1000,
        "message_type": "occupancy_event",
    })

    assert response.status_code == 201
    assert client.get("/api/occupancy/current").get_json()["occupancy"] == 4


def test_calibration_is_visible_in_event_history(client):
    client.post("/api/occupancy/calibrate", json={"occupancy": 2})
    events = client.get("/api/occupancy/events?limit=10").get_json()["events"]

    assert len(events) == 2
    assert all(event["device_id"] == "keyboard-calibration" for event in events)
    assert all(event["message_type"] == "calibration_adjustment" for event in events)


@pytest.mark.parametrize("payload", [
    {},
    {"occupancy": 1, "delta": 1},
    {"occupancy": -1},
    {"occupancy": 1001},
    {"occupancy": 1.5},
    {"occupancy": True},
    {"delta": 1001},
    {"delta": -1001},
    {"delta": 1.5},
    {"delta": False},
])
def test_calibration_rejects_invalid_values(client, payload):
    response = client.post("/api/occupancy/calibrate", json=payload)
    assert response.status_code == 400


def test_calibration_rejects_non_json(client):
    response = client.post(
        "/api/occupancy/calibrate",
        data="occupancy=3",
        content_type="text/plain",
    )
    assert response.status_code == 400
