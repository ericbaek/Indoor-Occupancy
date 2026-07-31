"""
ble_service.py
==============
Service logic for BLE tracking: RSSI smoothing, distance estimation,
position estimation, and zone classification.
"""

from __future__ import annotations

import statistics
import math
from typing import Any

from . import ble_config
from .database import get_recent_bluetooth_readings, _utc_now

# In-memory state for tracking tags between requests.
# Keys are tag_ids, values are dicts containing:
# - 'smoothed_position': {'x': float, 'y': float} (EMA smoothed)
# - 'stable_zone': str
# - 'candidate_zone': str
# - 'zone_candidate_since': str (ISO timestamp)
# - 'last_seen': str (ISO timestamp)
_tag_state: dict[str, dict[str, Any]] = {}


def get_tag_position(tag_id: str) -> dict[str, Any]:
    """Calculate and return the full position data for a tag."""
    now = _utc_now()
    window_s = ble_config.BLE_SETTINGS["rssi_window_seconds"]
    inactive_timeout = ble_config.BLE_SETTINGS["inactive_timeout_seconds"]

    # 1. Fetch recent readings
    readings = get_recent_bluetooth_readings(tag_id, window_seconds=window_s)
    
    if not readings:
        return _build_inactive_response(tag_id, "unknown", None)

    last_seen_at = readings[-1]["received_at"]

    # Check if inactive timeout exceeded
    from datetime import datetime, timezone
    last_dt = datetime.fromisoformat(last_seen_at)
    now_dt = datetime.now(timezone.utc)
    if (now_dt - last_dt).total_seconds() > inactive_timeout:
        return _build_inactive_response(tag_id, "outside", last_seen_at)

    # 2. Smooth RSSI (median per anchor)
    smoothed_rssi = smooth_rssi(readings)

    # 3. RSSI to distance
    distances = {
        anchor: rssi_to_distance(rssi, anchor)
        for anchor, rssi in smoothed_rssi.items()
        if rssi_to_distance(rssi, anchor) is not None
    }

    # 4. Coordinate estimation
    experimental_pos = estimate_position(distances)

    # 5. Coordinate smoothing
    smoothed_pos = smooth_position(tag_id, experimental_pos)

    # 6. Stable Zone estimation
    stable_zone = estimate_zone(tag_id, smoothed_rssi, smoothed_pos, last_seen_at)

    strongest_anchor, max_rssi = None, -999
    if smoothed_rssi:
        strongest_anchor = max(smoothed_rssi.items(), key=lambda x: x[1])[0]
        max_rssi = smoothed_rssi[strongest_anchor]

    # Calculate confidence based on the strongest RSSI (roughly mapping -90 to 0 and -40 to 100, clamped)
    confidence = int(max(0, min(100, (max_rssi + 90) * 2))) if max_rssi > -999 else 0

    return {
        "tag_id": tag_id,
        "status": "inside",
        "zone": _get_coordinate_zone(smoothed_pos) if smoothed_pos else "unknown",
        "stable_zone": stable_zone,
        "position": smoothed_pos,
        "strongest_scanner": strongest_anchor,
        "confidence_db": confidence,
        "scanner_rssi": smoothed_rssi,
        "estimated_distances": distances,
        "last_seen_at": last_seen_at,
    }


def _build_inactive_response(tag_id: str, zone: str, last_seen: str | None) -> dict[str, Any]:
    return {
        "tag_id": tag_id,
        "status": "inactive" if zone == "outside" else "unseen",
        "zone": zone,
        "stable_zone": zone,
        "position": None,
        "strongest_scanner": None,
        "confidence_db": 0,
        "scanner_rssi": {},
        "estimated_distances": {},
        "last_seen_at": last_seen,
    }


def smooth_rssi(readings: list[dict[str, Any]]) -> dict[str, float]:
    """Calculate the median RSSI for each anchor from recent readings."""
    grouped = {}
    for r in readings:
        anchor = r["scanner_id"]
        grouped.setdefault(anchor, []).append(r["rssi"])
    
    smoothed = {}
    for anchor, values in grouped.items():
        if not values:
            continue
        # Calculate median to reject extreme outliers like -80 when normally -50
        smoothed[anchor] = statistics.median(values)
    
    return smoothed


def rssi_to_distance(rssi: float, anchor_id: str) -> float | None:
    """Convert RSSI to distance using the log-distance path loss model."""
    calib = ble_config.ANCHOR_CALIBRATION.get(anchor_id)
    if not calib:
        return None
    
    ref_rssi = calib["reference_rssi_at_1m"]
    n = calib["path_loss_exponent"]
    
    # distance = 10 ^ ((reference_rssi - measured_rssi) / (10 * n))
    power = (ref_rssi - rssi) / (10.0 * n)
    try:
        dist = math.pow(10, power)
    except OverflowError:
        return None
        
    # Clamp to configured max distance
    max_dist = ble_config.BLE_SETTINGS["max_distance_metres"]
    return min(dist, max_dist)


def estimate_position(distances: dict[str, float]) -> dict[str, Any] | None:
    """Estimate (x,y) coordinate using Inverse-Distance Weighted Centroid.
    
    This is an acceptable fallback/primary method that doesn't require SciPy.
    It weights the position of each anchor inversely proportional to the 
    estimated distance.
    """
    min_anchors = ble_config.BLE_SETTINGS["min_anchors_for_position"]
    valid_distances = {k: v for k, v in distances.items() if k in ble_config.ANCHOR_POSITIONS}
    
    if len(valid_distances) < min_anchors:
        return None

    total_weight = 0.0
    weighted_x = 0.0
    weighted_y = 0.0

    for anchor, dist in valid_distances.items():
        # Avoid division by zero for extremely close tags
        safe_dist = max(0.1, dist)
        # Weight = 1 / distance^2
        weight = 1.0 / (safe_dist * safe_dist)
        
        pos = ble_config.ANCHOR_POSITIONS[anchor]
        weighted_x += pos["x"] * weight
        weighted_y += pos["y"] * weight
        total_weight += weight

    if total_weight == 0:
        return None

    x = weighted_x / total_weight
    y = weighted_y / total_weight

    # Clamp to room boundaries
    x = max(0.0, min(x, ble_config.ROOM_DIMENSIONS["width"]))
    y = max(0.0, min(y, ble_config.ROOM_DIMENSIONS["height"]))

    # Quality metric (1.0 = best, 0.0 = worst) based on number of anchors and distances
    # A simplified metric for demonstration
    quality = min(1.0, len(valid_distances) / 3.0 * (1.0 - min(distances.values()) / ble_config.BLE_SETTINGS["max_distance_metres"]))

    return {
        "x": round(x, 2),
        "y": round(y, 2),
        "unit": "metres",
        "method": "weighted_centroid",
        "label": "experimental",
        "quality": round(quality, 2),
    }


def smooth_position(tag_id: str, new_pos: dict[str, Any] | None) -> dict[str, Any] | None:
    """Apply Exponential Moving Average (EMA) to smooth out position jumps."""
    if not new_pos:
        return None
        
    state = _tag_state.setdefault(tag_id, {})
    prev_pos = state.get("smoothed_position")
    
    if not prev_pos:
        state["smoothed_position"] = {"x": new_pos["x"], "y": new_pos["y"]}
        return new_pos
        
    alpha = ble_config.BLE_SETTINGS["position_ema_alpha"]
    
    smoothed_x = prev_pos["x"] + alpha * (new_pos["x"] - prev_pos["x"])
    smoothed_y = prev_pos["y"] + alpha * (new_pos["y"] - prev_pos["y"])
    
    smoothed = {
        "x": round(smoothed_x, 2),
        "y": round(smoothed_y, 2),
        "unit": new_pos["unit"],
        "method": new_pos["method"],
        "label": new_pos["label"],
        "quality": new_pos["quality"],
    }
    
    state["smoothed_position"] = {"x": smoothed_x, "y": smoothed_y}
    return smoothed


def _get_coordinate_zone(pos: dict[str, Any] | None) -> str | None:
    """Map a coordinate to a predefined room zone."""
    if not pos:
        return None
        
    x, y = pos["x"], pos["y"]
    for zone, bounds in ble_config.ZONE_BOUNDARIES.items():
        if (bounds["x_min"] <= x <= bounds["x_max"] and
            bounds["y_min"] <= y <= bounds["y_max"]):
            return zone
            
    return None


def estimate_zone(tag_id: str, smoothed_rssi: dict[str, float], pos: dict[str, Any] | None, timestamp: str) -> str:
    """Estimate a stable zone using hysteresis to prevent rapid flapping."""
    if not smoothed_rssi:
        return "unknown"

    # 1. Determine the raw candidate zone
    candidate = None
    
    # Strategy A: Use the strongest anchor if it's clear
    sorted_anchors = sorted(smoothed_rssi.items(), key=lambda x: x[1], reverse=True)
    if len(sorted_anchors) >= 1:
        strongest, max_rssi = sorted_anchors[0]
        
        # Check if it's clearly the strongest or if we're in the centre
        if len(sorted_anchors) >= 2:
            second_strongest, second_rssi = sorted_anchors[1]
            diff = max_rssi - second_rssi
            if diff < ble_config.BLE_SETTINGS["centre_rssi_threshold_db"]:
                candidate = "centre"
                
        if not candidate:
            # Map strongest anchor to its zone
            if strongest in ble_config.ANCHOR_POSITIONS:
                candidate = ble_config.ANCHOR_POSITIONS[strongest]["zone"]
    
    # Strategy B: Compare with coordinate zone
    coord_zone = _get_coordinate_zone(pos)
    if coord_zone and candidate and coord_zone == candidate:
        # High confidence, they agree
        pass
    elif coord_zone and not candidate:
        candidate = coord_zone

    if not candidate:
        candidate = "unknown"

    # 2. Apply hysteresis
    state = _tag_state.setdefault(tag_id, {})
    current_stable = state.get("stable_zone", "unknown")
    current_candidate = state.get("candidate_zone")
    
    if candidate == current_stable:
        # We're stable
        state["candidate_zone"] = candidate
        state["zone_candidate_since"] = timestamp
        return current_stable
        
    if candidate != current_candidate:
        # New candidate, start timing
        state["candidate_zone"] = candidate
        state["zone_candidate_since"] = timestamp
        return current_stable
        
    # Same candidate, check if hold time exceeded
    from datetime import datetime, timezone
    since_dt = datetime.fromisoformat(state["zone_candidate_since"])
    now_dt = datetime.fromisoformat(timestamp)
    hold_s = ble_config.BLE_SETTINGS["zone_hold_seconds"]
    
    if (now_dt - since_dt).total_seconds() >= hold_s:
        # Candidate has been stable long enough, promote it
        state["stable_zone"] = candidate
        state["zone_candidate_since"] = timestamp
        return candidate
        
    return current_stable
