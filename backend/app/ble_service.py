"""Two-zone Bluetooth tracking based only on smoothed RSSI comparison."""

from __future__ import annotations

import statistics
from typing import Any

from . import ble_config
from .database import get_active_tags, get_recent_bluetooth_readings


# Short-lived display state. Raw readings remain in SQLite.
_tag_state: dict[str, dict[str, Any]] = {}


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


def assign_zone(tag_id: str, window_rssi: dict[str, float]) -> str:
    """Assign a tag to left/right using a 5 dBm switching hysteresis.

    Both anchors are required for a first assignment. If one anchor briefly
    misses the tag later, the previous zone is retained instead of flapping.
    """
    state = _tag_state.setdefault(tag_id, {})
    current_zone = state.get("current_zone", "unknown")

    left_rssi = window_rssi.get("anchor-left")
    right_rssi = window_rssi.get("anchor-right")
    if left_rssi is None or right_rssi is None:
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


def get_tag_state(tag_id: str) -> dict[str, Any]:
    """Return the active zone and latest smoothed RSSI values for one tag."""
    window_seconds = float(ble_config.BLE_SETTINGS["rssi_window_seconds"])
    readings = get_recent_bluetooth_readings(tag_id, window_seconds)
    if not readings:
        _tag_state.pop(tag_id, None)
        return {
            "tag_id": tag_id,
            "status": "inactive",
            "current_zone": "unknown",
            "scanner_rssi": {},
            "active_scanners": [],
            "last_seen_at": None,
        }

    window_rssi = smooth_rssi(readings)
    state = _tag_state.setdefault(tag_id, {})

    # Retain the latest value from each laptop for display, while zone changes
    # are based only on anchors present in the current rolling window.
    latest_rssi = dict(state.get("scanner_rssi", {}))
    latest_rssi.update(window_rssi)
    current_zone = assign_zone(tag_id, window_rssi)
    last_seen_at = readings[-1]["received_at"]

    state.update({
        "current_zone": current_zone,
        "scanner_rssi": latest_rssi,
        "last_seen_at": last_seen_at,
    })

    return {
        "tag_id": tag_id,
        "status": "active",
        "current_zone": current_zone,
        "scanner_rssi": latest_rssi,
        "active_scanners": sorted(window_rssi),
        "last_seen_at": last_seen_at,
    }


def get_tracking_summary() -> dict[str, Any]:
    """Return unique active-tag counts for the left and right zones."""
    timeout = float(ble_config.BLE_SETTINGS["inactive_timeout_seconds"])
    active_rows = get_active_tags(inactive_timeout_seconds=timeout)
    active_tag_ids = {row["tag_id"] for row in active_rows}

    # Remove stale in-memory state at the same time tags leave the active count.
    for stale_tag_id in set(_tag_state) - active_tag_ids:
        _tag_state.pop(stale_tag_id, None)

    counts = {zone: 0 for zone in ble_config.ZONE_NAMES}
    tags: list[dict[str, Any]] = []
    for tag_id in sorted(active_tag_ids):
        tag = get_tag_state(tag_id)
        if tag["status"] != "active":
            continue
        tags.append(tag)
        zone = tag["current_zone"]
        if zone in counts:
            counts[zone] += 1

    return {
        "total_active_tags": len(tags),
        "zones": {zone: {"count": counts[zone]} for zone in ble_config.ZONE_NAMES},
        "tags": tags,
    }


# Preserve the existing URL/service call name for older clients, but its
# response is now zone-only and contains no distances or coordinates.
get_tag_position = get_tag_state
