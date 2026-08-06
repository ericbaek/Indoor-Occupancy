"""Configuration for the two-zone Bluetooth signal-strength heatmap."""

from __future__ import annotations

import os


ANCHOR_ZONES: dict[str, str] = {
    "left-anchor": "left",
    "right-anchor": "right",
}

ZONE_ANCHORS: dict[str, str] = {
    zone: anchor_id for anchor_id, zone in ANCHOR_ZONES.items()
}

ZONE_NAMES: tuple[str, str] = ("left", "right")
KNOWN_ANCHOR_IDS: set[str] = set(ANCHOR_ZONES)

# Different laptop adapters can have a consistent RSSI bias. These offsets
# are applied centrally before conversion to the 0-100 heatmap score.
ANCHOR_RSSI_OFFSET: dict[str, float] = {
    "left-anchor": float(os.environ.get("BLE_LEFT_RSSI_OFFSET", "0")),
    "right-anchor": float(os.environ.get("BLE_RIGHT_RSSI_OFFSET", "0")),
}

BLE_SETTINGS: dict[str, float | int] = {
    "scan_window_seconds": float(os.environ.get("BLE_SCAN_WINDOW_SECONDS", "4")),
    "strongest_signal_count": int(os.environ.get("BLE_STRONGEST_SIGNAL_COUNT", "3")),
    "minimum_rssi": float(os.environ.get("BLE_MINIMUM_RSSI", "-100")),
    "maximum_rssi": float(os.environ.get("BLE_MAXIMUM_RSSI", "-40")),
    "ema_alpha": float(os.environ.get("BLE_EMA_ALPHA", "0.3")),
    "anchor_timeout_seconds": float(os.environ.get("BLE_ANCHOR_TIMEOUT_SECONDS", "15")),
    "balanced_threshold": float(os.environ.get("BLE_BALANCED_THRESHOLD", "2")),
}
