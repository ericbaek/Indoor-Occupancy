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
    # Readings inside this rolling window are averaged per anchor.
    "rssi_window_seconds": 5.0,

    # A tag disappears from the active count after this period without data.
    "inactive_timeout_seconds": 5.0,

    # Once assigned, the other anchor must be at least this much stronger
    # before the tag changes sides.
    "zone_switch_threshold_db": 5.0,

    # Data retention for raw readings (hours).
    "retention_hours": 24,
}

KNOWN_SCANNER_IDS: set[str] = set(ANCHOR_ZONES)
