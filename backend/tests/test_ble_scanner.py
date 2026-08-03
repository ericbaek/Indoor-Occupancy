"""Pure tests for BLE advertiser identity and scanner filtering."""

from types import SimpleNamespace

import pytest

from scripts import ble_advertiser_windows, ble_scanner


def _device(address="AA:BB:CC:DD:EE:01", name=None):
    return SimpleNamespace(address=address, name=name)


def _advertisement(*, name=None, manufacturer_data=None, service_uuids=None, rssi=-55):
    return SimpleNamespace(
        local_name=name,
        manufacturer_data=manufacturer_data or {},
        service_uuids=service_uuids or [],
        rssi=rssi,
        tx_power=None,
    )


def test_windows_advertiser_payload_round_trip():
    payload = ble_advertiser_windows.build_payload("PC-LEFT")
    assert ble_scanner.parse_comp6733_device_id({0xFFFE: payload}) == "BT-PC-PC-LEFT"


@pytest.mark.parametrize("invalid", ["", "space here", "x" * 17, "slash/name"])
def test_windows_advertiser_rejects_invalid_ids(invalid):
    with pytest.raises(ValueError):
        ble_advertiser_windows.build_payload(invalid)


def test_project_pc_beacon_is_accepted_without_allowlist(monkeypatch):
    monkeypatch.setattr(ble_scanner, "TARGET_SELECTORS", set())
    monkeypatch.setattr(ble_scanner, "SCAN_ALL", False)
    identity = ble_scanner.identify_device(
        _device(),
        _advertisement(manufacturer_data={0xFFFE: b"C6733:RIGHT-1"}),
    )
    assert identity["device_id"] == "BT-PC-RIGHT-1"
    assert identity["device_name"] == "Bluetooth PC RIGHT-1"


def test_macos_service_uuid_is_accepted_without_local_name(monkeypatch):
    monkeypatch.setattr(ble_scanner, "TARGET_SELECTORS", set())
    monkeypatch.setattr(ble_scanner, "SCAN_ALL", False)
    identity = ble_scanner.identify_device(
        _device(),
        _advertisement(service_uuids=["c6733033-4d41-4300-4d41-433100000000"]),
    )
    assert identity["device_id"] == "ROOM-TAG-MAC1"
    assert identity["device_name"] == "Bluetooth Mac MAC1"


@pytest.mark.parametrize(
    "service_uuids",
    [[], ["not-a-uuid"], ["c6733033-4d41-4300-0000-000000000000"]],
)
def test_invalid_macos_service_uuid_is_ignored(service_uuids):
    assert ble_scanner.parse_comp6733_mac_device_id(service_uuids) is None


def test_existing_room_tag_is_still_accepted(monkeypatch):
    monkeypatch.setattr(ble_scanner, "TARGET_SELECTORS", set())
    monkeypatch.setattr(ble_scanner, "SCAN_ALL", False)
    identity = ble_scanner.identify_device(_device(), _advertisement(name="ROOM-TAG-01"))
    assert identity["device_id"] == "ROOM-TAG-01"


def test_generic_device_requires_allowlist(monkeypatch):
    monkeypatch.setattr(ble_scanner, "TARGET_SELECTORS", set())
    monkeypatch.setattr(ble_scanner, "SCAN_ALL", False)
    assert ble_scanner.identify_device(_device(name="Nick Laptop"), _advertisement()) is None


def test_generic_device_can_be_selected_by_address(monkeypatch):
    monkeypatch.setattr(ble_scanner, "TARGET_SELECTORS", {"aa:bb:cc:dd:ee:01"})
    monkeypatch.setattr(ble_scanner, "SCAN_ALL", False)
    identity = ble_scanner.identify_device(_device(name="Nick Laptop"), _advertisement())
    assert identity["device_id"].startswith("BT-ADDR-")
    assert identity["device_name"] == "Nick Laptop"


def test_same_address_produces_same_anonymous_id():
    assert ble_scanner._address_device_id("aa:bb:cc:dd:ee:01") == ble_scanner._address_device_id(
        "AA:BB:CC:DD:EE:01"
    )
