"""
ble_routes.py
=============
Flask blueprint for the BLE tracking API endpoints.
"""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from . import ble_config
from . import ble_service
from .database import insert_bluetooth_reading, get_active_tags

ble_api = Blueprint("ble_api", __name__, url_prefix="/api/bluetooth")


@ble_api.post("/readings")
def post_reading():
    """Accept and store a BLE RSSI reading from a laptop scanner."""
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    # Validate message_type
    if data.get("message_type") != "bluetooth_rssi":
        return jsonify({"error": "message_type must be 'bluetooth_rssi'"}), 400

    # Validate scanner_id
    scanner_id = data.get("scanner_id")
    if not isinstance(scanner_id, str) or not scanner_id.strip():
        return jsonify({"error": "scanner_id must be a non-empty string"}), 400
    scanner_id = scanner_id.strip()
    if scanner_id not in ble_config.KNOWN_SCANNER_IDS:
        return jsonify({"error": f"Unknown scanner_id: {scanner_id}"}), 400

    # Validate tag_id
    tag_id = data.get("tag_id")
    if not isinstance(tag_id, str) or not tag_id.strip():
        return jsonify({"error": "tag_id must be a non-empty string"}), 400
    tag_id = tag_id.strip()
    if not tag_id.startswith("ROOM-TAG-"):
        return jsonify({"error": "tag_id must begin with 'ROOM-TAG-'"}), 400

    # Validate rssi
    rssi = data.get("rssi")
    if isinstance(rssi, bool) or not isinstance(rssi, int):
        return jsonify({"error": "rssi must be an integer"}), 400
    if not (-120 <= rssi <= 0):
        return jsonify({"error": "rssi must be between -120 and 0"}), 400

    # Validate tx_power
    tx_power = data.get("tx_power")
    if tx_power is not None:
        if isinstance(tx_power, bool) or not isinstance(tx_power, int):
            return jsonify({"error": "tx_power must be an integer or null"}), 400

    # Store reading
    try:
        received_at = insert_bluetooth_reading(
            scanner_id=scanner_id,
            tag_id=tag_id,
            rssi=rssi,
            tx_power=tx_power,
        )
    except Exception as e:
        return jsonify({"error": "Database error"}), 500

    return jsonify({
        "success": True,
        "message": "Bluetooth reading recorded",
        "data": {
            "scanner_id": scanner_id,
            "tag_id": tag_id,
            "rssi": rssi,
            "received_at": received_at,
        },
    }), 201


@ble_api.get("/position/<tag_id>")
def get_position(tag_id: str):
    """Calculate and return the estimated position and zone of a specific tag."""
    tag_id = tag_id.strip()
    if not tag_id.startswith("ROOM-TAG-"):
        return jsonify({"error": "Invalid tag ID"}), 400
        
    position_data = ble_service.get_tag_position(tag_id)
    return jsonify(position_data), 200


@ble_api.get("/tags")
def list_tags():
    """Return all currently active participating tags."""
    timeout = ble_config.BLE_SETTINGS["inactive_timeout_seconds"]
    active_rows = get_active_tags(inactive_timeout_seconds=timeout)
    
    tags = []
    for row in active_rows:
        pos_data = ble_service.get_tag_position(row["tag_id"])
        if pos_data["status"] == "inside":
            tags.append({
                "tag_id": pos_data["tag_id"],
                "status": pos_data["status"],
                "stable_zone": pos_data["stable_zone"],
                "position": pos_data["position"],
                "last_seen_at": pos_data["last_seen_at"],
            })
            
    return jsonify({
        "active_tag_count": len(tags),
        "tags": tags,
    }), 200
