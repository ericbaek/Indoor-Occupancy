"""Tests for the two-zone Bluetooth RSSI tracker."""

from datetime import datetime, timedelta, timezone

import pytest

from app import ble_config
import app.ble_service as ble_service
from app.database import get_db


def _valid_reading(**overrides):
    payload = {
        "message_type": "bluetooth_rssi",
        "scanner_id": "anchor-left",
        "tag_id": "ROOM-TAG-01",
        "rssi": -61,
        "tx_power": None,
    }
    payload.update(overrides)
    return payload


def _post(client, **overrides):
    return client.post("/api/bluetooth/readings", json=_valid_reading(**overrides))


def _post_pair(client, tag_id: str, left_rssi: int, right_rssi: int):
    assert _post(
        client, tag_id=tag_id, scanner_id="anchor-left", rssi=left_rssi
    ).status_code == 201
    assert _post(
        client, tag_id=tag_id, scanner_id="anchor-right", rssi=right_rssi
    ).status_code == 201


@pytest.fixture(autouse=True)
def reset_bluetooth_state(app):
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM bluetooth_readings")
        db.commit()
    ble_service._tag_state.clear()
    yield
    ble_service._tag_state.clear()


def test_config_only_accepts_two_laptop_anchors():
    assert ble_config.KNOWN_SCANNER_IDS == {"anchor-left", "anchor-right"}
    assert ble_config.ZONE_NAMES == ("left", "right")
    assert ble_config.BLE_SETTINGS["zone_switch_threshold_db"] == 5.0


def test_post_reading_keeps_existing_scanner_contract(client):
    response = _post(client, scanner_id="anchor-left", rssi=-55)
    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["scanner_id"] == "anchor-left"
    assert body["data"]["tag_id"] == "ROOM-TAG-01"
    assert body["data"]["rssi"] == -55
    datetime.fromisoformat(body["data"]["received_at"])


@pytest.mark.parametrize("scanner_id", ["anchor-left", "anchor-right"])
def test_both_laptop_anchors_are_accepted(client, scanner_id):
    assert _post(client, scanner_id=scanner_id).status_code == 201


def test_removed_back_anchor_is_rejected(client):
    response = _post(client, scanner_id="anchor-back")
    assert response.status_code == 400
    assert "Unknown scanner_id" in response.get_json()["error"]


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"message_type": "wrong"}, "message_type"),
        ({"tag_id": "OTHER-01"}, "ROOM-TAG-"),
        ({"rssi": -121}, "between -120 and 0"),
        ({"rssi": 1}, "between -120 and 0"),
        ({"rssi": -55.5}, "integer"),
    ],
)
def test_post_validation_is_preserved(client, overrides, error):
    response = _post(client, **overrides)
    assert response.status_code == 400
    assert error in response.get_json()["error"]


def test_rolling_rssi_average_is_calculated_per_anchor():
    readings = [
        {"scanner_id": "anchor-left", "rssi": -50},
        {"scanner_id": "anchor-left", "rssi": -60},
        {"scanner_id": "anchor-left", "rssi": -70},
        {"scanner_id": "anchor-right", "rssi": -80},
        {"scanner_id": "unknown", "rssi": -10},
    ]
    assert ble_service.smooth_rssi(readings) == {
        "anchor-left": -60.0,
        "anchor-right": -80.0,
    }


def test_initial_zone_uses_stronger_smoothed_rssi():
    assert ble_service.assign_zone(
        "ROOM-TAG-01", {"anchor-left": -55, "anchor-right": -72}
    ) == "left"


def test_zone_does_not_switch_when_other_side_is_only_four_db_stronger():
    tag_id = "ROOM-TAG-01"
    assert ble_service.assign_zone(
        tag_id, {"anchor-left": -55, "anchor-right": -70}
    ) == "left"
    assert ble_service.assign_zone(
        tag_id, {"anchor-left": -64, "anchor-right": -60}
    ) == "left"


def test_zone_switches_when_other_side_is_at_least_five_db_stronger():
    tag_id = "ROOM-TAG-01"
    assert ble_service.assign_zone(
        tag_id, {"anchor-left": -55, "anchor-right": -70}
    ) == "left"
    assert ble_service.assign_zone(
        tag_id, {"anchor-left": -65, "anchor-right": -60}
    ) == "right"


def test_missing_anchor_retains_previous_zone():
    tag_id = "ROOM-TAG-01"
    ble_service.assign_zone(tag_id, {"anchor-left": -50, "anchor-right": -70})
    assert ble_service.assign_zone(tag_id, {"anchor-left": -90}) == "left"


def test_unseen_tag_returns_inactive_zone_only_response(client):
    response = client.get("/api/bluetooth/state/ROOM-TAG-99")
    assert response.status_code == 200
    assert response.get_json() == {
        "active_scanners": [],
        "current_zone": "unknown",
        "last_seen_at": None,
        "scanner_rssi": {},
        "status": "inactive",
        "tag_id": "ROOM-TAG-99",
    }


def test_single_anchor_waits_for_both_anchors_before_first_assignment(client):
    _post(client, tag_id="ROOM-TAG-01", scanner_id="anchor-left", rssi=-45)
    body = client.get("/api/bluetooth/tags").get_json()
    assert body["total_active_tags"] == 1
    assert body["zones"] == {"left": {"count": 0}, "right": {"count": 0}}
    assert body["tags"][0]["current_zone"] == "unknown"


def test_four_left_and_one_right_required_heatmap_scenario(client):
    for number in range(1, 5):
        _post_pair(client, f"ROOM-TAG-{number:02d}", left_rssi=-50, right_rssi=-72)
    _post_pair(client, "ROOM-TAG-05", left_rssi=-76, right_rssi=-49)

    response = client.get("/api/bluetooth/tags")
    assert response.status_code == 200
    body = response.get_json()
    assert body["total_active_tags"] == 5
    assert body["zones"] == {"left": {"count": 4}, "right": {"count": 1}}
    assert len({tag["tag_id"] for tag in body["tags"]}) == 5


def test_duplicate_readings_do_not_double_count_tag(client):
    for _ in range(4):
        _post_pair(client, "ROOM-TAG-01", left_rssi=-48, right_rssi=-70)

    body = client.get("/api/bluetooth/tags").get_json()
    assert body["total_active_tags"] == 1
    assert body["zones"]["left"]["count"] == 1


def test_count_api_tracks_three_unique_tags_without_double_counting(client):
    _post_pair(client, "ROOM-TAG-01", left_rssi=-48, right_rssi=-72)
    _post_pair(client, "ROOM-TAG-02", left_rssi=-52, right_rssi=-70)
    _post_pair(client, "ROOM-TAG-03", left_rssi=-74, right_rssi=-49)
    _post_pair(client, "ROOM-TAG-01", left_rssi=-49, right_rssi=-71)

    response = client.get("/api/bluetooth/count")
    assert response.status_code == 200
    assert response.get_json() == {
        "total_active_tags": 3,
        "zones": {"left": {"count": 2}, "right": {"count": 1}},
        "unassigned_count": 0,
        "inactive_timeout_seconds": 5.0,
    }


def test_count_api_reports_tag_waiting_for_second_anchor_as_unassigned(client):
    _post(client, tag_id="ROOM-TAG-01", scanner_id="anchor-left", rssi=-48)

    body = client.get("/api/bluetooth/count").get_json()
    assert body["total_active_tags"] == 1
    assert body["zones"] == {"left": {"count": 0}, "right": {"count": 0}}
    assert body["unassigned_count"] == 1


def test_inactive_tag_is_removed_after_timeout(app, client):
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO bluetooth_readings
                (scanner_id, tag_id, rssi, tx_power, received_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("anchor-left", "ROOM-TAG-OLD", -50, None, old_time),
        )
        db.commit()

    body = client.get("/api/bluetooth/tags").get_json()
    assert body["total_active_tags"] == 0
    assert body["zones"] == {"left": {"count": 0}, "right": {"count": 0}}


def test_state_response_contains_rssi_but_no_distance_or_coordinates(client):
    _post_pair(client, "ROOM-TAG-01", left_rssi=-52, right_rssi=-70)
    body = client.get("/api/bluetooth/position/ROOM-TAG-01").get_json()

    assert body["current_zone"] == "left"
    assert body["scanner_rssi"] == {"anchor-left": -52.0, "anchor-right": -70.0}
    assert "position" not in body
    assert "estimated_distances" not in body
    assert "x" not in body
    assert "y" not in body


def test_occupancy_status_exposes_flat_two_zone_counts_only(client):
    _post_pair(client, "ROOM-TAG-01", left_rssi=-50, right_rssi=-75)
    _post_pair(client, "ROOM-TAG-02", left_rssi=-80, right_rssi=-51)

    response = client.get("/api/occupancy/status")
    assert response.status_code == 200
    body = response.get_json()
    assert body["bluetooth_tag_count"] == 2
    assert body["bluetooth_zones"] == {"left": 1, "right": 1}
    assert "bluetooth_positions" not in body
