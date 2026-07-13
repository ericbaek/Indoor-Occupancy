from __future__ import annotations

from flask import Blueprint, jsonify, request

from .database import get_db, get_events, get_room_state, insert_event, reset_room
from .occupancy import compute_new_count, get_occupancy_level

api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/health")
def health():
    try:
        get_db()
        db_status = "connected"
    except Exception:
        db_status = "error"
    return jsonify({"status": "ok", "database": db_status}), 200


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
