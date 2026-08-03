"""Tests for maximum-five Bluetooth device counting and two-zone tracking."""

from datetime import datetime, timedelta, timezone

import pytest

from app import ble_config
import app.ble_service as ble_service
from app.database import get_db


def _valid_reading(**overrides):
    payload = {
        "message_type": "bluetooth_rssi",
        "scanner_id": "anchor-left",
        "device_id": "BT-PC-01",
        "device_name": "Test PC 01",
        "device_address": "AA:BB:CC:DD:EE:01",
        "rssi": -61,
        "tx_power": None,
    }
    payload.update(overrides)
    return payload


def _post(client, **overrides):
    return client.post("/api/bluetooth/readings", json=_valid_reading(**overrides))


def _post_pair(client, device_id: str, left_rssi: int, right_rssi: int):
    name = f"Computer {device_id}"
    assert _post(
        client,
        device_id=device_id,
        device_name=name,
        scanner_id="anchor-left",
        rssi=left_rssi,
    ).status_code == 201
    assert _post(
        client,
        device_id=device_id,
        device_name=name,
        scanner_id="anchor-right",
        rssi=right_rssi,
    ).status_code == 201


@pytest.fixture(autouse=True)
def reset_bluetooth_state(app):
    with app.app_context():
        db = get_db()
        db.execute("DELETE FROM bluetooth_readings")
        db.commit()
    ble_service._device_state.clear()
    ble_service._device_metadata.clear()
    yield
    ble_service._device_state.clear()
    ble_service._device_metadata.clear()


def test_config_supports_two_anchors_and_maximum_five_devices():
    assert ble_config.KNOWN_SCANNER_IDS == {"anchor-left", "anchor-right"}
    assert ble_config.ZONE_NAMES == ("left", "right")
    assert ble_config.BLE_SETTINGS["max_tracked_devices"] == 5
    assert ble_config.BLE_SETTINGS["zone_switch_threshold_db"] == 5.0


def test_post_accepts_real_bluetooth_device_identity(client):
    response = _post(client, device_id="BT-PC-LAPTOP-1", rssi=-55)
    assert response.status_code == 201
    body = response.get_json()
    assert body["success"] is True
    assert body["data"]["device_id"] == "BT-PC-LAPTOP-1"
    assert body["data"]["device_name"] == "Test PC 01"
    datetime.fromisoformat(body["data"]["received_at"])


def test_legacy_room_tag_payload_remains_accepted(client):
    payload = _valid_reading()
    payload.pop("device_id")
    payload["tag_id"] = "ROOM-TAG-01"
    response = client.post("/api/bluetooth/readings", json=payload)
    assert response.status_code == 201
    assert response.get_json()["data"]["device_id"] == "ROOM-TAG-01"


@pytest.mark.parametrize("scanner_id", ["anchor-left", "anchor-right"])
def test_both_anchor_ids_are_accepted(client, scanner_id):
    assert _post(client, scanner_id=scanner_id).status_code == 201


def test_unknown_third_anchor_is_rejected(client):
    response = _post(client, scanner_id="anchor-right-2")
    assert response.status_code == 400
    assert "Unknown scanner_id" in response.get_json()["error"]


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"message_type": "wrong"}, "message_type"),
        ({"device_id": "contains spaces"}, "device_id"),
        ({"device_id": "x" * 65}, "device_id"),
        ({"rssi": -121}, "between -120 and 0"),
        ({"rssi": -55.5}, "integer"),
        ({"device_name": ""}, "device_name"),
    ],
)
def test_reading_validation(client, overrides, error):
    response = _post(client, **overrides)
    assert response.status_code == 400
    assert error in response.get_json()["error"]


def test_rolling_average_is_separate_per_anchor():
    readings = [
        {"scanner_id": "anchor-left", "rssi": -50},
        {"scanner_id": "anchor-left", "rssi": -60},
        {"scanner_id": "anchor-right", "rssi": -80},
    ]
    assert ble_service.smooth_rssi(readings) == {
        "anchor-left": -55.0,
        "anchor-right": -80.0,
    }


def test_initial_zone_uses_stronger_anchor():
    assert ble_service.assign_zone(
        "BT-PC-01", {"anchor-left": -55, "anchor-right": -72}
    ) == "left"


def test_zone_switch_requires_five_db_advantage():
    device_id = "BT-PC-01"
    ble_service.assign_zone(device_id, {"anchor-left": -55, "anchor-right": -70})
    assert ble_service.assign_zone(
        device_id, {"anchor-left": -64, "anchor-right": -60}
    ) == "left"
    assert ble_service.assign_zone(
        device_id, {"anchor-left": -65, "anchor-right": -60}
    ) == "right"


@pytest.mark.parametrize(
    ("scanner_rssi", "expected"),
    [
        ({"anchor-left": -20}, "left"),
        ({"anchor-right": -20}, "right"),
        ({"anchor-left": -50}, "unknown"),
    ],
)
def test_strong_self_heartbeat_classifies_anchor_pc(scanner_rssi, expected):
    assert ble_service.assign_zone("BT-PC-SELF", scanner_rssi) == expected


def test_three_actual_computer_identities_are_counted_and_split(client):
    _post_pair(client, "BT-PC-LEFT", left_rssi=-20, right_rssi=-70)
    _post_pair(client, "BT-PC-RIGHT-1", left_rssi=-72, right_rssi=-20)
    _post_pair(client, "BT-PC-RIGHT-2", left_rssi=-74, right_rssi=-48)

    body = client.get("/api/bluetooth/devices").get_json()
    assert body["total_active_devices"] == 3
    assert body["zones"] == {"left": {"count": 1}, "right": {"count": 2}}
    assert {device["device_id"] for device in body["devices"]} == {
        "BT-PC-LEFT",
        "BT-PC-RIGHT-1",
        "BT-PC-RIGHT-2",
    }


def test_duplicate_observations_never_double_count(client):
    for _ in range(4):
        _post_pair(client, "BT-PC-01", left_rssi=-48, right_rssi=-70)
    body = client.get("/api/bluetooth/devices").get_json()
    assert body["total_active_devices"] == 1
    assert body["zones"]["left"]["count"] == 1


def test_only_first_five_active_devices_are_counted(client):
    for number in range(1, 7):
        _post_pair(
            client,
            f"BT-PC-{number}",
            left_rssi=-50 if number <= 3 else -75,
            right_rssi=-72 if number <= 3 else -49,
        )

    body = client.get("/api/bluetooth/devices").get_json()
    assert body["total_active_devices"] == 5
    assert body["max_devices"] == 5
    assert body["ignored_active_devices"] == 1
    assert len(body["devices"]) == 5


def test_count_api_returns_device_count_and_heatmap_counts(client):
    _post_pair(client, "BT-PC-LEFT", left_rssi=-48, right_rssi=-72)
    _post_pair(client, "BT-PC-RIGHT-1", left_rssi=-72, right_rssi=-48)
    _post_pair(client, "BT-PC-RIGHT-2", left_rssi=-74, right_rssi=-49)

    body = client.get("/api/bluetooth/count").get_json()
    assert body == {
        "total_active_devices": 3,
        "total_active_tags": 3,
        "max_devices": 5,
        "zones": {"left": {"count": 1}, "right": {"count": 2}},
        "unassigned_count": 0,
        "ignored_active_devices": 0,
        "inactive_timeout_seconds": 5.0,
    }


def test_normal_single_anchor_reading_is_unassigned(client):
    _post(client, device_id="BT-PHONE-01", scanner_id="anchor-left", rssi=-55)
    body = client.get("/api/bluetooth/count").get_json()
    assert body["total_active_devices"] == 1
    assert body["unassigned_count"] == 1


def test_inactive_device_is_removed_after_timeout(app, client):
    old_time = (datetime.now(timezone.utc) - timedelta(seconds=30)).isoformat()
    with app.app_context():
        db = get_db()
        db.execute(
            """
            INSERT INTO bluetooth_readings
                (scanner_id, tag_id, rssi, tx_power, received_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("anchor-left", "BT-PC-OLD", -50, None, old_time),
        )
        db.commit()

    assert client.get("/api/bluetooth/devices").get_json()["total_active_devices"] == 0


def test_device_state_has_identity_rssi_and_no_coordinates(client):
    _post_pair(client, "BT-PC-01", left_rssi=-52, right_rssi=-70)
    body = client.get("/api/bluetooth/state/BT-PC-01").get_json()
    assert body["device_id"] == "BT-PC-01"
    assert body["device_name"] == "Computer BT-PC-01"
    assert body["current_zone"] == "left"
    assert body["scanner_rssi"] == {"anchor-left": -52.0, "anchor-right": -70.0}
    assert "position" not in body
    assert "estimated_distances" not in body


def test_occupancy_status_exposes_device_and_legacy_counts(client):
    _post_pair(client, "BT-PC-LEFT", left_rssi=-50, right_rssi=-75)
    _post_pair(client, "BT-PC-RIGHT", left_rssi=-80, right_rssi=-51)

    body = client.get("/api/occupancy/status").get_json()
    assert body["bluetooth_device_count"] == 2
    assert body["bluetooth_tag_count"] == 2
    assert body["bluetooth_zones"] == {"left": 1, "right": 1}
    assert "bluetooth_positions" not in body
