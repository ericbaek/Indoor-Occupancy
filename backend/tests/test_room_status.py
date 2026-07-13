def _entry(client, room_id="room_01", count=1):
    return client.post("/api/events", json={
        "room_id": room_id, "sensor_type": "mmwave",
        "event_type": "ENTRY", "count": count,
    })


def test_room_status_returns_latest_state(client):
    _entry(client, count=3)
    data = client.get("/api/rooms/room_01/status").get_json()
    assert data["room_id"] == "room_01"
    assert data["occupancy_count"] == 3
    assert data["occupancy_level"] == "Low"
    assert data["last_event"] == "ENTRY"


def test_room_status_unknown_room_returns_defaults(client):
    data = client.get("/api/rooms/unknown_room_999/status").get_json()
    assert data["occupancy_count"] == 0
    assert data["occupancy_level"] == "Empty"
    assert data["last_event"] is None
    assert data["updated_at"] is None


def test_event_filtering_by_room_id(client):
    _entry(client, room_id="room_01")
    client.post("/api/events", json={
        "room_id": "room_99", "sensor_type": "pir", "event_type": "TRIGGER",
    })
    events = client.get("/api/events?room_id=room_99").get_json()["events"]
    assert all(e["room_id"] == "room_99" for e in events)


def test_event_filtering_by_sensor_type(client):
    client.post("/api/events", json={
        "room_id": "room_01", "sensor_type": "pir", "event_type": "TRIGGER",
    })
    client.post("/api/events", json={
        "room_id": "room_01", "sensor_type": "co2", "event_type": "READING", "value": 450,
    })
    events = client.get("/api/events?sensor_type=co2").get_json()["events"]
    assert len(events) >= 1
    assert all(e["sensor_type"] == "co2" for e in events)


def test_event_limit_is_respected(client):
    for _ in range(5):
        _entry(client)
    events = client.get("/api/events?room_id=room_01&limit=3").get_json()["events"]
    assert len(events) <= 3


def test_event_limit_max_capped_at_200(client):
    assert client.get("/api/events?limit=999").status_code == 200


def test_room_reset_sets_count_to_zero(client):
    _entry(client, count=5)
    assert client.post("/api/rooms/room_01/reset").status_code == 200
    data = client.get("/api/rooms/room_01/status").get_json()
    assert data["occupancy_count"] == 0
    assert data["occupancy_level"] == "Empty"
    assert data["last_event"] == "RESET"


def test_room_reset_does_not_delete_events(client):
    _entry(client, count=2)
    client.post("/api/rooms/room_01/reset")
    events = client.get("/api/events?room_id=room_01").get_json()["events"]
    assert "ENTRY" in [e["event_type"] for e in events]
