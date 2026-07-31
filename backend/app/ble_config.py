"""
ble_config.py
=============
Central configuration for the BLE tracking subsystem.

**IMPORTANT: Replace all default values with real measured values before
running an experiment.**

Measurement checklist
---------------------
1. Measure the room width and height with a tape measure.
2. Agree on the room coordinate origin (0, 0) — recommended: front-left corner.
3. Place the three anchor laptops at fixed positions and measure their (x, y)
   coordinates in metres from the origin.
4. Place the Nano tag exactly 1 metre from each anchor in turn and collect
   RSSI readings for at least 30 seconds; use the median as reference_rssi_at_1m.
5. Measure RSSI at 2 m, 3 m, 5 m and fit a path-loss exponent per anchor.
6. Update ANCHOR_POSITIONS and ANCHOR_CALIBRATION below.
7. Update ROOM_DIMENSIONS and ZONE_BOUNDARIES to match the real room layout.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Room dimensions (metres).
# Replace these with real measured values.
# ---------------------------------------------------------------------------

ROOM_DIMENSIONS: dict[str, float] = {
    "width": 6.0,   # x axis (left → right)
    "height": 5.0,  # y axis (front → back)
}

# ---------------------------------------------------------------------------
# Anchor positions (metres) and which zone each anchor "represents".
# Three Windows laptops must be placed at these fixed positions.
#
# Replace x/y with real measurements.  The origin (0, 0) should be the
# front-left corner of the room so that x increases to the right and
# y increases toward the back wall.
# ---------------------------------------------------------------------------

ANCHOR_POSITIONS: dict[str, dict] = {
    "anchor-left": {
        "x": 0.0,
        "y": 0.0,
        "zone": "left",
    },
    "anchor-right": {
        "x": 6.0,
        "y": 0.0,
        "zone": "right",
    },
    "anchor-back": {
        "x": 3.0,
        "y": 5.0,
        "zone": "back",
    },
}

# ---------------------------------------------------------------------------
# Per-anchor RSSI-to-distance calibration.
#
# reference_rssi_at_1m:  median RSSI (dBm, negative) measured at exactly 1 m.
# path_loss_exponent:    n in the log-distance model (2.0 = free space;
#                        2.2–3.5 is typical indoors).
#
# Each laptop's Bluetooth adapter has slightly different transmit power and
# antenna gain, so calibrate each anchor separately.
# ---------------------------------------------------------------------------

ANCHOR_CALIBRATION: dict[str, dict] = {
    "anchor-left": {
        "reference_rssi_at_1m": -50.0,
        "path_loss_exponent": 2.2,
    },
    "anchor-right": {
        "reference_rssi_at_1m": -51.0,
        "path_loss_exponent": 2.2,
    },
    "anchor-back": {
        "reference_rssi_at_1m": -49.0,
        "path_loss_exponent": 2.2,
    },
}

# ---------------------------------------------------------------------------
# Zone boundaries (metres).
# Each zone is a rectangle [x_min, x_max] × [y_min, y_max].
# Adjust to match the real room layout.
# ---------------------------------------------------------------------------

ZONE_BOUNDARIES: dict[str, dict[str, float]] = {
    "left": {
        "x_min": 0.0,
        "x_max": 2.0,
        "y_min": 0.0,
        "y_max": 5.0,
    },
    "centre": {
        "x_min": 2.0,
        "x_max": 4.0,
        "y_min": 0.0,
        "y_max": 3.5,
    },
    "right": {
        "x_min": 4.0,
        "x_max": 6.0,
        "y_min": 0.0,
        "y_max": 5.0,
    },
    "back": {
        "x_min": 2.0,
        "x_max": 4.0,
        "y_min": 3.5,
        "y_max": 5.0,
    },
}

# ---------------------------------------------------------------------------
# Algorithm tuning parameters.
# ---------------------------------------------------------------------------

BLE_SETTINGS: dict[str, float | int] = {
    # Width of the RSSI smoothing window in seconds.
    "rssi_window_seconds": 2.0,

    # A tag is considered "outside" / inactive if no reading has been seen
    # within this many seconds.
    "inactive_timeout_seconds": 5.0,

    # If the two strongest anchor RSSI values differ by less than this many
    # dBm, the tag is considered to be in "centre".
    "centre_rssi_threshold_db": 4.0,

    # A candidate zone must remain stable for this long (seconds) before it
    # replaces the current displayed zone (anti-flapping hysteresis).
    "zone_hold_seconds": 1.5,

    # Exponential moving-average factor for coordinate smoothing (0–1).
    # Lower = smoother but slower to react; higher = more responsive but noisier.
    "position_ema_alpha": 0.3,

    # Maximum distance (metres) to accept from RSSI-to-distance conversion.
    # Values beyond this are clamped to this bound.
    "max_distance_metres": 20.0,

    # Minimum number of anchors required to attempt coordinate estimation.
    "min_anchors_for_position": 2,

    # Data retention for raw readings (hours).
    "retention_hours": 24,
}

# ---------------------------------------------------------------------------
# Recognised scanner IDs.
# The POST /api/bluetooth/readings endpoint rejects unknown scanner_ids.
# Add any additional scanner IDs here if you add a fourth laptop.
# ---------------------------------------------------------------------------

KNOWN_SCANNER_IDS: set[str] = set(ANCHOR_POSITIONS.keys())
