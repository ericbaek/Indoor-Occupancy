def _entry(client, room_id="room_01", count=1):
    return client.post("/api/events", json={
        "room_id": room_id,
        "device_id": "door_sensor_01",
        "sensor_type": "mmwave",
        "event_type": "ENTRY",
        "count": count,
    })


def _exit(client, room_id="room_01", count=1):
    return client.post("/api/events", json={
        "room_id": room_id,
        "device_id": "door_sensor_01",
        "sensor_type": "mmwave",
        "event_type": "EXIT",
        "count": count,
    })


def test_missing_json_body_returns_400(client):
    response = client.post("/api/events", data="not json", content_type="text/plain")
    assert response.status_code == 400


def test_missing_required_fields_returns_400(client):
    assert client.post("/api/events", json={"room_id": "room_01"}).status_code == 400


def test_missing_sensor_type_returns_400(client):
    assert client.post("/api/events", json={"room_id": "room_01", "event_type": "ENTRY"}).status_code == 400


def test_missing_event_type_returns_400(client):
    assert client.post("/api/events", json={"room_id": "room_01", "sensor_type": "mmwave"}).status_code == 400


def test_empty_room_id_returns_400(client):
    assert client.post("/api/events", json={
        "room_id": "   ", "sensor_type": "mmwave", "event_type": "ENTRY"
    }).status_code == 400


def test_non_numeric_value_returns_400(client):
    assert client.post("/api/events", json={
        "room_id": "room_01", "sensor_type": "co2", "event_type": "READING", "value": "high"
    }).status_code == 400


def test_non_positive_count_returns_400(client):
    assert client.post("/api/events", json={
        "room_id": "room_01", "sensor_type": "mmwave", "event_type": "ENTRY", "count": 0
    }).status_code == 400


def test_negative_count_returns_400(client):
    assert client.post("/api/events", json={
        "room_id": "room_01", "sensor_type": "mmwave", "event_type": "ENTRY", "count": -1
    }).status_code == 400


def test_entry_increases_occupancy(client):
    data = _entry(client, count=1).get_json()
    assert data["occupancy_count"] == 1
    assert data["occupancy_level"] == "Low"


def test_exit_decreases_occupancy(client):
    _entry(client, count=3)
    assert _exit(client, count=1).get_json()["occupancy_count"] == 2


def test_exit_never_makes_occupancy_negative(client):
    assert _exit(client, count=5).get_json()["occupancy_count"] == 0


def test_multiple_entry_events_accumulate(client):
    _entry(client, count=1)
    _entry(client, count=2)
    assert _entry(client, count=1).get_json()["occupancy_count"] == 4


def test_pir_trigger_stored_without_changing_occupancy(client):
    _entry(client, count=2)
    data = client.post("/api/events", json={
        "room_id": "room_01", "device_id": "pir_out_01",
        "sensor_type": "pir", "event_type": "TRIGGER",
        "position": "OUTSIDE", "state": 1,
    }).get_json()
    assert data["occupancy_count"] == 2


def test_mmwave_frame_stored_without_changing_occupancy(client):
    _entry(client, count=3)
    data = client.post("/api/events", json={
        "room_id": "room_01", "device_id": "rd03d_01",
        "sensor_type": "mmwave", "event_type": "FRAME",
        "target_count": 1,
        "targets": [{"target_id": 1, "angle_deg": -6.23, "distance_mm": 469.78, "speed_cm_s": 0}],
    }).get_json()
    assert data["occupancy_count"] == 3


def test_co2_reading_stored_without_changing_occupancy(client):
    _entry(client, count=1)
    data = client.post("/api/events", json={
        "room_id": "room_01", "device_id": "scd41_01",
        "sensor_type": "co2", "event_type": "READING", "value": 782,
    }).get_json()
    assert data["occupancy_count"] == 1


def test_complete_raw_payload_is_retained(client):
    client.post("/api/events", json={
        "room_id": "room_01", "device_id": "pir_out_01",
        "sensor_type": "pir", "event_type": "TRIGGER",
        "position": "OUTSIDE", "state": 1, "extra_field": "extra_value",
    })
    events = client.get("/api/events?room_id=room_01&sensor_type=pir&limit=1").get_json()["events"]
    payload = events[0]["payload"]
    assert payload["position"] == "OUTSIDE"
    assert payload["extra_field"] == "extra_value"
    assert payload["state"] == 1


def test_zero_mmwave_targets_can_be_stored(client):
    client.post("/api/events", json={
        "room_id": "room_01", "device_id": "rd03d_01",
        "sensor_type": "mmwave", "event_type": "FRAME",
        "target_count": 0, "targets": [],
    })
    events = client.get("/api/events?room_id=room_01&event_type=FRAME&limit=1").get_json()["events"]
    assert events[0]["payload"]["targets"] == []


def test_one_mmwave_target_can_be_stored(client):
    client.post("/api/events", json={
        "room_id": "room_01", "device_id": "rd03d_01",
        "sensor_type": "mmwave", "event_type": "FRAME",
        "target_count": 1,
        "targets": [{"target_id": 1, "angle_deg": -6.23, "distance_mm": 469.78, "speed_cm_s": 0}],
    })
    events = client.get("/api/events?room_id=room_01&event_type=FRAME&limit=1").get_json()["events"]
    assert len(events[0]["payload"]["targets"]) == 1
    assert events[0]["payload"]["targets"][0]["angle_deg"] == -6.23


def test_three_mmwave_targets_can_be_stored(client):
    client.post("/api/events", json={
        "room_id": "room_01", "device_id": "rd03d_01",
        "sensor_type": "mmwave", "event_type": "FRAME",
        "target_count": 3,
        "targets": [
            {"target_id": 1, "angle_deg": -6.23, "distance_mm": 469.78, "speed_cm_s": 0},
            {"target_id": 2, "angle_deg": 12.5, "distance_mm": 1200.0, "speed_cm_s": 5},
            {"target_id": 3, "angle_deg": 0.0, "distance_mm": 800.0, "speed_cm_s": -3},
        ],
    })
    events = client.get("/api/events?room_id=room_01&event_type=FRAME&limit=1").get_json()["events"]
    assert len(events[0]["payload"]["targets"]) == 3
