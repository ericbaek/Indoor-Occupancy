"""Two-zone Bluetooth device counting based on smoothed RSSI comparison."""

from __future__ import annotations

import statistics
from typing import Any

from . import ble_config
from .database import get_active_tags, get_recent_bluetooth_readings


_device_state: dict[str, dict[str, Any]] = {}
_device_metadata: dict[str, dict[str, str | None]] = {}

# Backward-compatible name used by existing tests and development tooling.
_tag_state = _device_state


def register_device_metadata(
    device_id: str,
    *,
    device_name: str | None = None,
    device_address: str | None = None,
) -> None:
    metadata = _device_metadata.setdefault(device_id, {})
    if device_name:
        metadata["device_name"] = device_name
    if device_address:
        metadata["device_address"] = device_address


def smooth_rssi(readings: list[dict[str, Any]]) -> dict[str, float]:
    """Return the rolling arithmetic mean RSSI for each recognised anchor."""
    grouped: dict[str, list[float]] = {}
    for reading in readings:
        scanner_id = reading["scanner_id"]
        if scanner_id not in ble_config.KNOWN_SCANNER_IDS:
            continue
        grouped.setdefault(scanner_id, []).append(float(reading["rssi"]))

    return {
        scanner_id: round(statistics.fmean(values), 2)
        for scanner_id, values in grouped.items()
        if values
    }


def assign_zone(device_id: str, window_rssi: dict[str, float]) -> str:
    """Assign a device to left/right with rolling RSSI and 5 dBm hysteresis."""
    state = _device_state.setdefault(device_id, {})
    current_zone = state.get("current_zone", "unknown")
    left_rssi = window_rssi.get("anchor-left")
    right_rssi = window_rssi.get("anchor-right")

    # Anchor PCs cannot receive their own BLE packet. Their advertiser posts a
    # trusted -20 dBm self heartbeat while the BLE publisher is active.
    self_threshold = float(ble_config.BLE_SETTINGS["self_proximity_rssi_threshold"])
    if current_zone == "unknown" and right_rssi is None and left_rssi is not None:
        if left_rssi >= self_threshold:
            current_zone = "left"
    elif current_zone == "unknown" and left_rssi is None and right_rssi is not None:
        if right_rssi >= self_threshold:
            current_zone = "right"

    if left_rssi is None or right_rssi is None:
        state["current_zone"] = current_zone
        return current_zone

    threshold = float(ble_config.BLE_SETTINGS["zone_switch_threshold_db"])
    if current_zone == "unknown":
        current_zone = "left" if left_rssi >= right_rssi else "right"
    elif current_zone == "left" and right_rssi - left_rssi >= threshold:
        current_zone = "right"
    elif current_zone == "right" and left_rssi - right_rssi >= threshold:
        current_zone = "left"

    state["current_zone"] = current_zone
    return current_zone


def get_device_state(device_id: str) -> dict[str, Any]:
    """Return active zone, identity, and smoothed RSSI for one device."""
    window_seconds = float(ble_config.BLE_SETTINGS["rssi_window_seconds"])
    readings = get_recent_bluetooth_readings(device_id, window_seconds)
    metadata = _device_metadata.get(device_id, {})
    if not readings:
        _device_state.pop(device_id, None)
        return {
            "device_id": device_id,
            "tag_id": device_id,
            "device_name": metadata.get("device_name") or device_id,
            "device_address": metadata.get("device_address"),
            "status": "inactive",
            "current_zone": "unknown",
            "scanner_rssi": {},
            "active_scanners": [],
            "last_seen_at": None,
        }

    window_rssi = smooth_rssi(readings)
    state = _device_state.setdefault(device_id, {})
    latest_rssi = dict(state.get("scanner_rssi", {}))
    latest_rssi.update(window_rssi)
    current_zone = assign_zone(device_id, window_rssi)
    last_seen_at = readings[-1]["received_at"]

    state.update({
        "current_zone": current_zone,
        "scanner_rssi": latest_rssi,
        "last_seen_at": last_seen_at,
    })

    return {
        "device_id": device_id,
        "tag_id": device_id,
        "device_name": metadata.get("device_name") or device_id,
        "device_address": metadata.get("device_address"),
        "status": "active",
        "current_zone": current_zone,
        "scanner_rssi": latest_rssi,
        "active_scanners": sorted(window_rssi),
        "last_seen_at": last_seen_at,
    }


def get_tracking_summary() -> dict[str, Any]:
    """Return at most five unique active Bluetooth devices by room side."""
    timeout = float(ble_config.BLE_SETTINGS["inactive_timeout_seconds"])
    maximum = int(ble_config.BLE_SETTINGS["max_tracked_devices"])
    active_rows = get_active_tags(inactive_timeout_seconds=timeout)
    selected_rows = active_rows[:maximum]
    all_active_ids = {row["tag_id"] for row in active_rows}
    selected_ids = [row["tag_id"] for row in selected_rows]

    for stale_device_id in set(_device_state) - all_active_ids:
        _device_state.pop(stale_device_id, None)
        _device_metadata.pop(stale_device_id, None)

    counts = {zone: 0 for zone in ble_config.ZONE_NAMES}
    devices: list[dict[str, Any]] = []
    for device_id in selected_ids:
        device = get_device_state(device_id)
        if device["status"] != "active":
            continue
        devices.append(device)
        zone = device["current_zone"]
        if zone in counts:
            counts[zone] += 1

    zones = {zone: {"count": counts[zone]} for zone in ble_config.ZONE_NAMES}
    return {
        "total_active_devices": len(devices),
        "max_devices": maximum,
        "ignored_active_devices": max(0, len(active_rows) - maximum),
        "zones": zones,
        "devices": devices,
        # Compatibility fields for clients still using the earlier tag API.
        "total_active_tags": len(devices),
        "tags": devices,
    }


get_tag_state = get_device_state
get_tag_position = get_device_state
