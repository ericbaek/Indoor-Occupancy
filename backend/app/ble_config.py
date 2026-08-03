"""Configuration for the two-zone Bluetooth tracking subsystem.

The two Windows laptops are fixed anchors.  A tag is assigned to the side
whose smoothed RSSI is stronger; no distance or coordinate model is used.
"""

from __future__ import annotations


ANCHOR_ZONES: dict[str, str] = {
    "anchor-left": "left",
    "anchor-right": "right",
}

ZONE_NAMES: tuple[str, str] = ("left", "right")

BLE_SETTINGS: dict[str, float | int] = {
    # At most this many unique participating Bluetooth devices appear in the
    # room count. Extra ambient advertisers are reported as ignored.
    "max_tracked_devices": 5,

    # Readings inside this rolling window are averaged per anchor.
    "rssi_window_seconds": 5.0,

    # A tag disappears from the active count after this period without data.
    "inactive_timeout_seconds": 5.0,

    # Once assigned, the other anchor must be at least this much stronger
    # before the tag changes sides.
    "zone_switch_threshold_db": 5.0,

    # A single reading this strong is a trusted co-located-anchor heartbeat
    # from ble_advertiser_windows.py, used because an adapter cannot hear its
    # own advertisement.
    "self_proximity_rssi_threshold": -35.0,

    # Data retention for raw readings (hours).
    "retention_hours": 24,
}

KNOWN_SCANNER_IDS: set[str] = set(ANCHOR_ZONES)
