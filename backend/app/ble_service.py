"""Two-zone Bluetooth signal-strength state and smoothing.

The scanner reduces a short window of advertisements to one representative
RSSI value. The backend applies per-anchor calibration, converts RSSI to a
0-100 score, and smooths the score with an exponential moving average.

No device count, distance, coordinate, or person estimate is produced here.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from . import ble_config


_anchor_state: dict[str, dict[str, Any]] = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def reset_anchor_state() -> None:
    """Clear in-memory Bluetooth state. Used by tests and local demos."""
    _anchor_state.clear()


def rssi_to_score(rssi: float) -> float:
    """Linearly convert a calibrated RSSI value to a clamped 0-100 score."""
    minimum = float(ble_config.BLE_SETTINGS["minimum_rssi"])
    maximum = float(ble_config.BLE_SETTINGS["maximum_rssi"])
    if maximum <= minimum:
        raise ValueError("maximum_rssi must be greater than minimum_rssi")
    clamped = max(minimum, min(maximum, float(rssi)))
    return round((clamped - minimum) / (maximum - minimum) * 100.0, 2)


def record_anchor_signal(
    anchor_id: str,
    *,
    average_rssi: float | None,
    reported_signal_score: float,
    reported_at: str | None,
) -> dict[str, Any]:
    """Record one scanner window and return the current public snapshot."""
    now = _utc_now()
    offset = float(ble_config.ANCHOR_RSSI_OFFSET[anchor_id])
    calibrated_rssi = None if average_rssi is None else round(average_rssi + offset, 2)
    current_score = 0.0 if calibrated_rssi is None else rssi_to_score(calibrated_rssi)

    previous = _anchor_state.get(anchor_id)
    alpha = float(ble_config.BLE_SETTINGS["ema_alpha"])
    if previous is None:
        smoothed_score = current_score
    else:
        smoothed_score = (
            alpha * current_score
            + (1.0 - alpha) * float(previous["smoothed_signal_score"])
        )

    _anchor_state[anchor_id] = {
        "average_rssi": calibrated_rssi,
        "raw_average_rssi": average_rssi,
        "raw_signal_score": current_score,
        "reported_signal_score": reported_signal_score,
        "smoothed_signal_score": round(smoothed_score, 2),
        "calibration_offset_db": offset,
        "reported_at": reported_at,
        "received_at": now,
    }
    return get_anchor_snapshot(anchor_id, now=now)


def get_anchor_snapshot(
    anchor_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return active data or an offline snapshot when the anchor is stale."""
    now = now or _utc_now()
    zone = ble_config.ANCHOR_ZONES[anchor_id]
    state = _anchor_state.get(anchor_id)
    timeout = float(ble_config.BLE_SETTINGS["anchor_timeout_seconds"])

    if state is None or (now - state["received_at"]).total_seconds() > timeout:
        return {
            "anchor_id": anchor_id,
            "zone": zone,
            "status": "offline",
            "average_rssi": None,
            "signal_score": None,
            "last_seen_at": state["received_at"].isoformat() if state else None,
            "calibration_offset_db": float(ble_config.ANCHOR_RSSI_OFFSET[anchor_id]),
        }

    return {
        "anchor_id": anchor_id,
        "zone": zone,
        "status": "active",
        "average_rssi": state["average_rssi"],
        "signal_score": state["smoothed_signal_score"],
        "raw_signal_score": state["raw_signal_score"],
        "last_seen_at": state["received_at"].isoformat(),
        "reported_at": state["reported_at"],
        "calibration_offset_db": state["calibration_offset_db"],
    }


def get_signal_summary() -> dict[str, Any]:
    """Return the latest Left/Right signal intensity without device counts."""
    now = _utc_now()
    zones = {
        zone: get_anchor_snapshot(anchor_id, now=now)
        for zone, anchor_id in ble_config.ZONE_ANCHORS.items()
    }

    left = zones["left"]
    right = zones["right"]
    stronger_zone: str | None = None
    if left["status"] == "active" and right["status"] == "active":
        difference = float(left["signal_score"]) - float(right["signal_score"])
        threshold = float(ble_config.BLE_SETTINGS["balanced_threshold"])
        if abs(difference) < threshold:
            stronger_zone = "balanced"
        else:
            stronger_zone = "left" if difference > 0 else "right"

    return {
        "measurement": "relative_bluetooth_signal_intensity",
        "zones": zones,
        "stronger_zone": stronger_zone,
        "anchor_timeout_seconds": ble_config.BLE_SETTINGS["anchor_timeout_seconds"],
        "ema_alpha": ble_config.BLE_SETTINGS["ema_alpha"],
    }
