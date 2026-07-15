"""
Tests for PIR doorway occupancy event endpoints:
  POST /api/occupancy/events
  GET  /api/occupancy/current
  GET  /api/occupancy/events
"""

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_BASE_ENTRY = {
    "device_id": "doorway-pico-01",
    "event_id": 1,
    "event": "entry",
    "count_change": 1,
    "duration_ms": 2404,
    "uptime_ms": 508384,
}

_BASE_EXIT = {
    "device_id": "doorway-pico-01",
    "event_id": 2,
    "event": "exit",
    "count_change": -1,
    "duration_ms": 1222,
    "uptime_ms": 496909,
}


def _post(client, payload):
    return client.post("/api/occupancy/events", json=payload)


def _unique_entry(event_id: int, device_id: str = "test-pico-01") -> dict:
    """Return a valid entry payload with a unique (device_id, event_id) pair."""
    return {
        "device_id": device_id,
        "event_id": event_id,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 1000,
        "uptime_ms": 5000,
    }


def _unique_exit(event_id: int, device_id: str = "test-pico-01") -> dict:
    """Return a valid exit payload with a unique (device_id, event_id) pair."""
    return {
        "device_id": device_id,
        "event_id": event_id,
        "event": "exit",
        "count_change": -1,
        "duration_ms": 800,
        "uptime_ms": 6000,
    }


# ---------------------------------------------------------------------------
# POST /api/occupancy/events — valid events
# ---------------------------------------------------------------------------

def test_valid_entry_event_returns_201(client):
    response = _post(client, _BASE_ENTRY)
    assert response.status_code == 201


def test_valid_entry_event_returns_success_body(client):
    # Use a unique event_id to avoid a 409 from the preceding test.
    payload = {**_BASE_ENTRY, "event_id": 1001}
    data = _post(client, payload).get_json()
    assert data["success"] is True
    assert data["message"] == "Occupancy event recorded"
    assert data["data"]["device_id"] == "doorway-pico-01"
    assert data["data"]["event_id"] == 1001
    assert data["data"]["event"] == "entry"
    assert data["data"]["count_change"] == 1


def test_valid_exit_event_returns_201(client):
    response = _post(client, _BASE_EXIT)
    assert response.status_code == 201


def test_valid_exit_event_returns_success_body(client):
    # Use a unique event_id to avoid a 409 from the preceding test.
    payload = {**_BASE_EXIT, "event_id": 1002}
    data = _post(client, payload).get_json()
    assert data["success"] is True
    assert data["data"]["event"] == "exit"
    assert data["data"]["count_change"] == -1


# ---------------------------------------------------------------------------
# POST /api/occupancy/events — invalid event type
# ---------------------------------------------------------------------------

def test_invalid_event_type_returns_400(client):
    payload = {**_BASE_ENTRY, "event_id": 100, "event": "trigger"}
    assert _post(client, payload).status_code == 400


def test_invalid_event_type_uppercase_returns_400(client):
    # The hardware spec uses lowercase; uppercase "ENTRY" is not accepted.
    payload = {**_BASE_ENTRY, "event_id": 101, "event": "ENTRY"}
    assert _post(client, payload).status_code == 400


def test_invalid_event_type_error_message(client):
    payload = {**_BASE_ENTRY, "event_id": 102, "event": "trigger"}
    data = _post(client, payload).get_json()
    assert "event" in data["error"]


# ---------------------------------------------------------------------------
# POST /api/occupancy/events — mismatched event and count_change
# ---------------------------------------------------------------------------

def test_entry_with_negative_count_change_returns_400(client):
    payload = {**_BASE_ENTRY, "event_id": 110, "count_change": -1}
    assert _post(client, payload).status_code == 400


def test_exit_with_positive_count_change_returns_400(client):
    payload = {**_BASE_EXIT, "event_id": 111, "count_change": 1}
    assert _post(client, payload).status_code == 400


def test_mismatch_error_message_mentions_count_change(client):
    payload = {**_BASE_ENTRY, "event_id": 112, "count_change": -1}
    data = _post(client, payload).get_json()
    assert "count_change" in data["error"]


# ---------------------------------------------------------------------------
# POST /api/occupancy/events — duplicate device_id + event_id
# ---------------------------------------------------------------------------

def test_duplicate_event_returns_409(client):
    _post(client, _BASE_ENTRY)
    response = _post(client, _BASE_ENTRY)
    assert response.status_code == 409


def test_duplicate_event_error_mentions_device_and_event_id(client):
    _post(client, _BASE_ENTRY)
    data = _post(client, _BASE_ENTRY).get_json()
    assert "doorway-pico-01" in data["error"]
    assert "1" in data["error"]


def test_same_event_id_different_device_is_accepted(client):
    payload_a = {**_BASE_ENTRY, "device_id": "device-A"}
    payload_b = {**_BASE_ENTRY, "device_id": "device-B"}
    assert _post(client, payload_a).status_code == 201
    assert _post(client, payload_b).status_code == 201


# ---------------------------------------------------------------------------
# POST /api/occupancy/events — negative duration_ms
# ---------------------------------------------------------------------------

def test_negative_duration_ms_returns_400(client):
    payload = {**_BASE_ENTRY, "event_id": 120, "duration_ms": -1}
    assert _post(client, payload).status_code == 400


def test_zero_duration_ms_is_accepted(client):
    payload = {**_BASE_ENTRY, "event_id": 121, "duration_ms": 0}
    assert _post(client, payload).status_code == 201


# ---------------------------------------------------------------------------
# POST /api/occupancy/events — negative uptime_ms
# ---------------------------------------------------------------------------

def test_negative_uptime_ms_returns_400(client):
    payload = {**_BASE_ENTRY, "event_id": 130, "uptime_ms": -1}
    assert _post(client, payload).status_code == 400


def test_zero_uptime_ms_is_accepted(client):
    payload = {**_BASE_ENTRY, "event_id": 131, "uptime_ms": 0}
    assert _post(client, payload).status_code == 201


# ---------------------------------------------------------------------------
# GET /api/occupancy/current — occupancy calculation
# ---------------------------------------------------------------------------

def test_current_occupancy_key_exists_and_is_non_negative(client):
    # The session-scoped database accumulates events from all tests, so we
    # cannot assert a specific value of zero here.  Instead we verify that
    # the response always contains a non-negative integer.
    data = client.get("/api/occupancy/current").get_json()
    assert "occupancy" in data
    assert isinstance(data["occupancy"], int)
    assert data["occupancy"] >= 0


def test_current_occupancy_after_entries(client):
    # Use a dedicated device to avoid clashing with other tests in the
    # session-scoped database.
    _post(client, _unique_entry(10, "calc-pico"))
    _post(client, _unique_entry(11, "calc-pico"))
    _post(client, _unique_entry(12, "calc-pico"))
    data = client.get("/api/occupancy/current").get_json()
    assert data["occupancy"] >= 3


def test_current_occupancy_decreases_on_exit(client):
    _post(client, _unique_entry(20, "calc2-pico"))
    _post(client, _unique_entry(21, "calc2-pico"))
    _post(client, _unique_exit(22, "calc2-pico"))
    data = client.get("/api/occupancy/current").get_json()
    assert data["occupancy"] >= 1


def test_current_occupancy_includes_updated_at_when_events_exist(client):
    _post(client, _unique_entry(30, "ts-pico"))
    data = client.get("/api/occupancy/current").get_json()
    assert data["updated_at"] is not None


# ---------------------------------------------------------------------------
# GET /api/occupancy/current — occupancy never goes below zero
# ---------------------------------------------------------------------------

def test_occupancy_never_goes_below_zero(client):
    # Only exits from a fresh device — the clamp must prevent negative values.
    _post(client, _unique_exit(40, "floor-pico"))
    _post(client, _unique_exit(41, "floor-pico"))
    _post(client, _unique_exit(42, "floor-pico"))
    data = client.get("/api/occupancy/current").get_json()
    assert data["occupancy"] >= 0


def test_occupancy_response_is_never_negative(client):
    # Post nothing; the endpoint must always return a non-negative integer.
    data = client.get("/api/occupancy/current").get_json()
    assert data["occupancy"] >= 0


# ---------------------------------------------------------------------------
# GET /api/occupancy/events — list events
# ---------------------------------------------------------------------------

def test_list_occupancy_events_returns_200(client):
    assert client.get("/api/occupancy/events").status_code == 200


def test_list_occupancy_events_newest_first(client):
    _post(client, _unique_entry(60, "order-pico"))
    _post(client, _unique_exit(61, "order-pico"))
    events = client.get("/api/occupancy/events").get_json()["events"]
    ids = [e["id"] for e in events]
    assert ids == sorted(ids, reverse=True)


def test_list_occupancy_events_limit_is_respected(client):
    for i in range(70, 80):
        _post(client, _unique_entry(i, "limit-pico"))
    events = client.get("/api/occupancy/events?limit=3").get_json()["events"]
    assert len(events) <= 3


def test_list_occupancy_events_contains_required_fields(client):
    _post(client, _unique_entry(90, "field-pico"))
    events = client.get("/api/occupancy/events?limit=1").get_json()["events"]
    assert len(events) >= 1
    row = events[0]
    for field in ("id", "device_id", "event_id", "event",
                  "count_change", "duration_ms", "uptime_ms", "received_at"):
        assert field in row, f"Missing field: {field}"
