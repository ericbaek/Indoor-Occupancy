from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from flask import Blueprint, jsonify, request

from .database import (
    get_db,
    get_environment_history,
    get_environment_latest_all,
    get_environment_latest_for_device,
    get_events,
    get_occupancy_events,
    get_occupancy_total,
    get_radar_latest_all,
    get_radar_latest_for_device,
    get_room_state,
    insert_environment_reading_if_throttled,
    insert_event,
    insert_occupancy_event,
    insert_radar_reading_if_throttled,
    reset_room,
    upsert_environment_latest,
    upsert_radar_latest,
)
from .occupancy import compute_new_count, get_occupancy_level

api = Blueprint("api", __name__, url_prefix="/api")

# ---------------------------------------------------------------------------
# In-memory mismatch tracking for the /api/occupancy/status endpoint.
# Keyed by device_id → ISO timestamp string when mismatch began (or None).
# This is a simple prototype-level approach; no persistence across restarts.
# ---------------------------------------------------------------------------
_mismatch_started_at: str | None = None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@api.get("/health")
def health():
    try:
        get_db()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return jsonify({"status": "ok", "database": db_status}), 200


# ---------------------------------------------------------------------------
# Legacy sensor events (room-based)
# ---------------------------------------------------------------------------

@api.post("/events")
def post_event():
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    missing = [f for f in ("room_id", "sensor_type", "event_type") if f not in data]
    if missing:
        return jsonify({"error": f"Missing required field(s): {', '.join(missing)}"}), 400

    room_id: str = str(data["room_id"]).strip()
    sensor_type: str = str(data["sensor_type"]).strip().lower()
    event_type: str = str(data["event_type"]).strip().upper()

    if not room_id:
        return jsonify({"error": "room_id must not be empty"}), 400
    if not sensor_type:
        return jsonify({"error": "sensor_type must not be empty"}), 400
    if not event_type:
        return jsonify({"error": "event_type must not be empty"}), 400

    value: float | None = None
    if "value" in data:
        raw_value = data["value"]
        if not isinstance(raw_value, (int, float)) or isinstance(raw_value, bool):
            return jsonify({"error": "value must be a number"}), 400
        value = float(raw_value)

    raw_count = data.get("count")
    event_count: int
    if raw_count is not None:
        if isinstance(raw_count, bool) or not isinstance(raw_count, int) or raw_count < 1:
            return jsonify({"error": "count must be a positive integer"}), 400
        event_count = raw_count
    else:
        event_count = 1

    device_id: str | None = data.get("device_id")
    if device_id is not None:
        device_id = str(device_id).strip() or None

    row = get_room_state(room_id)
    current_count: int = row["occupancy_count"] if row else 0

    new_count = compute_new_count(current_count, event_type, event_count)
    new_level = get_occupancy_level(new_count)

    event_id, updated_at = insert_event(
        room_id=room_id,
        device_id=device_id,
        sensor_type=sensor_type,
        event_type=event_type,
        value=value,
        event_count=event_count if event_type in ("ENTRY", "EXIT") else None,
        occupancy_count=new_count,
        occupancy_level=new_level,
        payload=data,
    )

    return jsonify({
        "message": "Event stored successfully",
        "event_id": event_id,
        "room_id": room_id,
        "occupancy_count": new_count,
        "occupancy_level": new_level,
        "updated_at": updated_at,
    }), 201


@api.get("/rooms/<room_id>/status")
def room_status(room_id: str):
    room_id = room_id.strip()
    row = get_room_state(room_id)

    if row is None:
        return jsonify({
            "room_id": room_id,
            "occupancy_count": 0,
            "occupancy_level": "Empty",
            "last_event": None,
            "updated_at": None,
        }), 200

    return jsonify({
        "room_id": row["room_id"],
        "occupancy_count": row["occupancy_count"],
        "occupancy_level": row["occupancy_level"],
        "last_event": row["last_event"],
        "updated_at": row["updated_at"],
    }), 200


@api.get("/events")
def list_events():
    room_id = request.args.get("room_id") or None
    sensor_type = request.args.get("sensor_type") or None
    event_type = request.args.get("event_type") or None

    try:
        limit = max(1, int(request.args.get("limit", "50")))
    except ValueError:
        limit = 50

    if sensor_type:
        sensor_type = sensor_type.strip().lower()
    if event_type:
        event_type = event_type.strip().upper()

    events = get_events(
        room_id=room_id,
        sensor_type=sensor_type,
        event_type=event_type,
        limit=limit,
    )

    return jsonify({"events": events}), 200


@api.post("/rooms/<room_id>/reset")
def room_reset(room_id: str):
    room_id = room_id.strip()
    updated_at = reset_room(room_id)

    return jsonify({
        "message": f"Room {room_id!r} has been reset",
        "room_id": room_id,
        "occupancy_count": 0,
        "occupancy_level": "Empty",
        "last_event": "RESET",
        "updated_at": updated_at,
    }), 200


# ---------------------------------------------------------------------------
# PIR doorway occupancy events
# ---------------------------------------------------------------------------

_VALID_EVENTS = {"entry", "exit"}
_EVENT_COUNT_CHANGE = {"entry": 1, "exit": -1}


@api.post("/occupancy/events")
def post_occupancy_event():
    """Accept and store a PIR doorway occupancy event from hardware.

    The hardware JSON format includes optional 'message_type' and 'radar'
    fields.  Requests that omit these fields (older format) are still accepted
    for backward compatibility.
    """
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    # --- Required field presence check ---
    required = ("device_id", "event_id", "event", "count_change",
                "duration_ms", "uptime_ms")
    missing = [f for f in required if f not in data]
    if missing:
        return jsonify(
            {"error": f"Missing required field(s): {', '.join(missing)}"}
        ), 400

    # --- device_id ---
    device_id: str = str(data["device_id"]).strip()
    if not device_id:
        return jsonify({"error": "device_id must not be empty"}), 400

    # --- event_id ---
    raw_event_id = data["event_id"]
    if isinstance(raw_event_id, bool) or not isinstance(raw_event_id, int):
        return jsonify({"error": "event_id must be an integer"}), 400
    event_id: int = raw_event_id

    # --- event ---
    raw_event = data["event"]
    if not isinstance(raw_event, str) or raw_event not in _VALID_EVENTS:
        return jsonify(
            {"error": f"event must be one of: {', '.join(sorted(_VALID_EVENTS))}"}
        ), 400
    event: str = raw_event

    # --- count_change: must be an integer and match the event type ---
    raw_cc = data["count_change"]
    if isinstance(raw_cc, bool) or not isinstance(raw_cc, int):
        return jsonify({"error": "count_change must be an integer"}), 400
    count_change: int = raw_cc

    expected_cc = _EVENT_COUNT_CHANGE[event]
    if count_change != expected_cc:
        return jsonify({
            "error": (
                f"count_change must be {expected_cc} for an '{event}' event, "
                f"got {count_change}"
            )
        }), 400

    # --- duration_ms ---
    raw_duration = data["duration_ms"]
    if isinstance(raw_duration, bool) or not isinstance(raw_duration, int):
        return jsonify({"error": "duration_ms must be an integer"}), 400
    if raw_duration < 0:
        return jsonify({"error": "duration_ms must be zero or greater"}), 400
    duration_ms: int = raw_duration

    # --- uptime_ms ---
    raw_uptime = data["uptime_ms"]
    if isinstance(raw_uptime, bool) or not isinstance(raw_uptime, int):
        return jsonify({"error": "uptime_ms must be an integer"}), 400
    if raw_uptime < 0:
        return jsonify({"error": "uptime_ms must be zero or greater"}), 400
    uptime_ms: int = raw_uptime

    # --- Optional: message_type ---
    message_type: str | None = None
    if "message_type" in data:
        raw_mt = data["message_type"]
        if not isinstance(raw_mt, str):
            return jsonify({"error": "message_type must be a string"}), 400
        if raw_mt != "occupancy_event":
            return jsonify({
                "error": "message_type must be 'occupancy_event' for this endpoint"
            }), 400
        message_type = raw_mt

    # --- Optional: radar snapshot ---
    radar_target_count: int | None = None
    radar_targets_json: str | None = None

    if "radar" in data:
        radar = data["radar"]
        if not isinstance(radar, dict):
            return jsonify({"error": "radar must be an object"}), 400

        # radar.target_count
        raw_rtc = radar.get("target_count")
        if raw_rtc is None:
            return jsonify({"error": "radar.target_count is required"}), 400
        if isinstance(raw_rtc, bool) or not isinstance(raw_rtc, int):
            return jsonify({"error": "radar.target_count must be an integer"}), 400
        if raw_rtc < 0 or raw_rtc > 3:
            return jsonify({"error": "radar.target_count must be between 0 and 3"}), 400
        radar_target_count = raw_rtc

        # radar.targets
        raw_targets = radar.get("targets")
        if raw_targets is None:
            return jsonify({"error": "radar.targets is required"}), 400
        if not isinstance(raw_targets, list):
            return jsonify({"error": "radar.targets must be an array"}), 400
        if len(raw_targets) != radar_target_count:
            return jsonify({
                "error": (
                    f"radar.target_count ({radar_target_count}) does not match "
                    f"length of radar.targets ({len(raw_targets)})"
                )
            }), 400
        radar_targets_json = json.dumps(raw_targets)

    # --- Store event ---
    import sqlite3 as _sqlite3
    try:
        _row_id, received_at = insert_occupancy_event(
            device_id=device_id,
            event_id=event_id,
            event=event,
            count_change=count_change,
            duration_ms=duration_ms,
            uptime_ms=uptime_ms,
            message_type=message_type,
            radar_target_count=radar_target_count,
            radar_targets_json=radar_targets_json,
        )
    except _sqlite3.IntegrityError:
        return jsonify({
            "error": (
                f"Duplicate event: device_id '{device_id}' and "
                f"event_id {event_id} already recorded"
            )
        }), 409

    return jsonify({
        "success": True,
        "message": "Occupancy event recorded",
        "data": {
            "device_id": device_id,
            "event_id": event_id,
            "event": event,
            "count_change": count_change,
        },
    }), 201


@api.get("/occupancy/current")
def get_current_occupancy():
    """Return the current occupancy derived from the sum of all count_change values."""
    occupancy, updated_at = get_occupancy_total()
    return jsonify({
        "occupancy": occupancy,
        "updated_at": updated_at,
    }), 200


@api.get("/occupancy/events")
def list_occupancy_events():
    """Return recent PIR occupancy events, newest first."""
    try:
        limit = max(1, int(request.args.get("limit", "50")))
    except ValueError:
        limit = 50

    events = get_occupancy_events(limit=limit)
    return jsonify({"events": events}), 200


# ---------------------------------------------------------------------------
# Radar readings
# ---------------------------------------------------------------------------

_REQUIRED_TARGET_FIELDS = (
    "target_id", "x_mm", "y_mm", "distance_mm", "angle_deg", "speed_cm_s"
)
_NUMERIC_TARGET_FIELDS = (
    "target_id", "x_mm", "y_mm", "distance_mm", "angle_deg", "speed_cm_s"
)


def _validate_target(target: Any, index: int) -> str | None:
    """Validate a single radar target dict.  Returns an error string or None."""
    if not isinstance(target, dict):
        return f"targets[{index}] must be an object"
    for field in _REQUIRED_TARGET_FIELDS:
        if field not in target:
            return f"targets[{index}] is missing required field '{field}'"
    for field in _NUMERIC_TARGET_FIELDS:
        val = target[field]
        if isinstance(val, bool) or not isinstance(val, (int, float)):
            return f"targets[{index}].{field} must be a number"
    return None


@api.post("/radar/readings")
def post_radar_reading():
    """Accept and store a radar reading from hardware (via the gateway script)."""
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    # --- message_type ---
    if data.get("message_type") != "radar":
        return jsonify({"error": "message_type must be 'radar'"}), 400

    # --- device_id ---
    raw_device = data.get("device_id", "")
    if not isinstance(raw_device, str) or not raw_device.strip():
        return jsonify({"error": "device_id must be a non-empty string"}), 400
    device_id = raw_device.strip()

    # --- uptime_ms ---
    raw_uptime = data.get("uptime_ms")
    if raw_uptime is None:
        return jsonify({"error": "Missing required field: uptime_ms"}), 400
    if isinstance(raw_uptime, bool) or not isinstance(raw_uptime, (int, float)):
        return jsonify({"error": "uptime_ms must be a number"}), 400
    if raw_uptime < 0:
        return jsonify({"error": "uptime_ms must be zero or greater"}), 400
    uptime_ms = int(raw_uptime)

    # --- target_count ---
    raw_tc = data.get("target_count")
    if raw_tc is None:
        return jsonify({"error": "Missing required field: target_count"}), 400
    if isinstance(raw_tc, bool) or not isinstance(raw_tc, int):
        return jsonify({"error": "target_count must be an integer"}), 400
    if raw_tc < 0 or raw_tc > 3:
        return jsonify({"error": "target_count must be between 0 and 3"}), 400
    target_count = raw_tc

    # --- targets ---
    raw_targets = data.get("targets")
    if raw_targets is None:
        return jsonify({"error": "Missing required field: targets"}), 400
    if not isinstance(raw_targets, list):
        return jsonify({"error": "targets must be an array"}), 400
    if len(raw_targets) != target_count:
        return jsonify({
            "error": (
                f"target_count ({target_count}) does not match "
                f"length of targets ({len(raw_targets)})"
            )
        }), 400

    for i, target in enumerate(raw_targets):
        err = _validate_target(target, i)
        if err:
            return jsonify({"error": err}), 400

    # --- Persist ---
    received_at = upsert_radar_latest(
        device_id=device_id,
        uptime_ms=uptime_ms,
        target_count=target_count,
        targets=raw_targets,
    )
    insert_radar_reading_if_throttled(
        device_id=device_id,
        uptime_ms=uptime_ms,
        target_count=target_count,
        targets=raw_targets,
    )

    return jsonify({
        "success": True,
        "message": "Radar reading recorded",
        "data": {
            "device_id": device_id,
            "target_count": target_count,
            "received_at": received_at,
        },
    }), 201


# ---------------------------------------------------------------------------
# Radar query endpoints
# ---------------------------------------------------------------------------

@api.get("/radar/latest")
def get_radar_latest():
    """Return the latest radar snapshot for all known devices."""
    devices = get_radar_latest_all()
    return jsonify({"devices": devices}), 200


@api.get("/radar/latest/<device_id>")
def get_radar_latest_device(device_id: str):
    """Return the latest radar snapshot for a specific device."""
    device_id = device_id.strip()
    snapshot = get_radar_latest_for_device(device_id)
    if snapshot is None:
        return jsonify({
            "error": f"No radar data found for device_id '{device_id}'"
        }), 404
    return jsonify(snapshot), 200


# ---------------------------------------------------------------------------
# Environment / CO2 sensor readings
# ---------------------------------------------------------------------------

@api.post("/co2/readings")
def post_environment_reading():
    """Accept and store an environment reading from the CO2 sensor hardware."""
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    # --- message_type ---
    if data.get("message_type") != "environment":
        return jsonify({"error": "message_type must be 'environment'"}), 400

    # --- device_id ---
    raw_device = data.get("device_id", "")
    if not isinstance(raw_device, str) or not raw_device.strip():
        return jsonify({"error": "device_id must be a non-empty string"}), 400
    device_id = raw_device.strip()

    # --- uptime_ms ---
    raw_uptime = data.get("uptime_ms")
    if raw_uptime is None:
        return jsonify({"error": "Missing required field: uptime_ms"}), 400
    if isinstance(raw_uptime, bool) or not isinstance(raw_uptime, (int, float)):
        return jsonify({"error": "uptime_ms must be a number"}), 400
    if raw_uptime < 0:
        return jsonify({"error": "uptime_ms must be zero or greater"}), 400
    uptime_ms = int(raw_uptime)

    # --- co2_ppm ---
    raw_co2 = data.get("co2_ppm")
    if raw_co2 is None:
        return jsonify({"error": "Missing required field: co2_ppm"}), 400
    if isinstance(raw_co2, bool) or not isinstance(raw_co2, (int, float)):
        return jsonify({"error": "co2_ppm must be a number"}), 400
    if raw_co2 < 0:
        return jsonify({"error": "co2_ppm must be zero or greater"}), 400
    co2_ppm = int(raw_co2)

    # --- temperature_c ---
    raw_temp = data.get("temperature_c")
    if raw_temp is None:
        return jsonify({"error": "Missing required field: temperature_c"}), 400
    if isinstance(raw_temp, bool) or not isinstance(raw_temp, (int, float)):
        return jsonify({"error": "temperature_c must be a number"}), 400
    temperature_c = float(raw_temp)

    # --- humidity_percent ---
    raw_hum = data.get("humidity_percent")
    if raw_hum is None:
        return jsonify({"error": "Missing required field: humidity_percent"}), 400
    if isinstance(raw_hum, bool) or not isinstance(raw_hum, (int, float)):
        return jsonify({"error": "humidity_percent must be a number"}), 400
    if raw_hum < 0 or raw_hum > 100:
        return jsonify({"error": "humidity_percent must be between 0 and 100"}), 400
    humidity_percent = float(raw_hum)

    # --- Persist ---
    received_at = upsert_environment_latest(
        device_id=device_id,
        uptime_ms=uptime_ms,
        co2_ppm=co2_ppm,
        temperature_c=temperature_c,
        humidity_percent=humidity_percent,
    )
    insert_environment_reading_if_throttled(
        device_id=device_id,
        uptime_ms=uptime_ms,
        co2_ppm=co2_ppm,
        temperature_c=temperature_c,
        humidity_percent=humidity_percent,
    )

    return jsonify({
        "success": True,
        "message": "Environment reading recorded",
        "data": {
            "device_id": device_id,
            "co2_ppm": co2_ppm,
            "temperature_c": temperature_c,
            "humidity_percent": humidity_percent,
            "received_at": received_at,
        },
    }), 201


# ---------------------------------------------------------------------------
# Environment query endpoints
# ---------------------------------------------------------------------------

@api.get("/co2/latest")
def get_environment_latest():
    """Return the latest environment reading for all known devices."""
    devices = get_environment_latest_all()
    return jsonify({"devices": devices}), 200


@api.get("/co2/latest/<device_id>")
def get_environment_latest_device(device_id: str):
    """Return the latest environment reading for a specific device."""
    device_id = device_id.strip()
    reading = get_environment_latest_for_device(device_id)
    if reading is None:
        return jsonify({
            "error": f"No CO2 data found for device_id '{device_id}'"
        }), 404
    return jsonify(reading), 200


@api.get("/co2/history/<device_id>")
def get_environment_history_endpoint(device_id: str):
    """Return recent environment readings for a device, newest first."""
    device_id = device_id.strip()
    try:
        limit = max(1, int(request.args.get("limit", "50")))
    except ValueError:
        limit = 50

    readings = get_environment_history(device_id, limit=limit)
    return jsonify({"device_id": device_id, "readings": readings}), 200


# ---------------------------------------------------------------------------
# CO2 level classification
# ---------------------------------------------------------------------------

def _co2_level(ppm: int) -> str:
    """Classify a CO2 reading using ASHRAE-based thresholds.

    - normal:   < 800 ppm  (typical outdoor / empty room)
    - elevated: 800–1500 ppm (suggests people are present)
    - high:     > 1500 ppm (multiple people or poor ventilation)
    """
    if ppm < 800:
        return "normal"
    if ppm <= 1500:
        return "elevated"
    return "high"


# ---------------------------------------------------------------------------
# Unified occupancy status endpoint (for the frontend)
# ---------------------------------------------------------------------------

@api.get("/occupancy/status")
def get_occupancy_status():
    """Return a unified view of PIR occupancy, radar presence, and CO2 level.

    Status rules:
    - 'confirmed'  when occupancy count and radar presence agree.
    - 'uncertain'  when they disagree (e.g. occupancy > 0 but no radar
                   targets, or occupancy = 0 but radar sees targets).

    The mismatch_started_at timestamp records when the disagreement began.
    Note: radar data alone never causes the occupancy count to change
    automatically — this is intentional to account for the ~10-second
    mmWave detection delay.
    """
    global _mismatch_started_at

    occupancy, last_occupancy_event_at = get_occupancy_total()

    # Aggregate radar across all devices — use the device with the highest
    # target_count as the representative snapshot.
    devices = get_radar_latest_all()
    radar_target_count = 0
    last_radar_update_at: str | None = None

    for dev in devices:
        if dev["target_count"] > radar_target_count:
            radar_target_count = dev["target_count"]
        if last_radar_update_at is None or dev["received_at"] > last_radar_update_at:
            last_radar_update_at = dev["received_at"]

    radar_presence = radar_target_count > 0

    # Aggregate environment / CO2 across all devices — use the device with
    # the highest CO2 reading as the representative value.
    env_devices = get_environment_latest_all()
    co2_ppm: int | None = None
    temperature_c: float | None = None
    humidity_percent: float | None = None
    last_environment_update_at: str | None = None

    for env in env_devices:
        if co2_ppm is None or env["co2_ppm"] > co2_ppm:
            co2_ppm = env["co2_ppm"]
            temperature_c = env["temperature_c"]
            humidity_percent = env["humidity_percent"]
        if last_environment_update_at is None or env["received_at"] > last_environment_update_at:
            last_environment_update_at = env["received_at"]

    co2_level_str: str | None = _co2_level(co2_ppm) if co2_ppm is not None else None

    # Determine confirmed vs uncertain.
    occupancy_present = occupancy > 0
    agreed = (occupancy_present == radar_presence)

    now_str = datetime.now(timezone.utc).isoformat()

    if agreed:
        status = "confirmed"
        _mismatch_started_at = None
    else:
        status = "uncertain"
        if _mismatch_started_at is None:
            _mismatch_started_at = now_str

    return jsonify({
        "occupancy": occupancy,
        "status": status,
        "radar_presence": radar_presence,
        "radar_target_count": radar_target_count,
        "co2_ppm": co2_ppm,
        "co2_level": co2_level_str,
        "temperature_c": temperature_c,
        "humidity_percent": humidity_percent,
        "last_occupancy_event_at": last_occupancy_event_at,
        "last_radar_update_at": last_radar_update_at,
        "last_environment_update_at": last_environment_update_at,
        "mismatch_started_at": _mismatch_started_at,
    }), 200
