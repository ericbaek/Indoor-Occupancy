"""Flask endpoints for Bluetooth device counting and two-zone tracking."""

from __future__ import annotations

import re

from flask import Blueprint, jsonify, request

from . import ble_config, ble_service
from .database import insert_bluetooth_reading


ble_api = Blueprint("ble_api", __name__, url_prefix="/api/bluetooth")
DEVICE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9:._-]{0,63}$")


def _valid_device_id(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value if DEVICE_ID_PATTERN.fullmatch(value) else None


@ble_api.post("/readings")
def post_reading():
    """Accept one RSSI observation from a fixed laptop anchor."""
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400
    if data.get("message_type") != "bluetooth_rssi":
        return jsonify({"error": "message_type must be 'bluetooth_rssi'"}), 400

    scanner_id = data.get("scanner_id")
    if not isinstance(scanner_id, str) or not scanner_id.strip():
        return jsonify({"error": "scanner_id must be a non-empty string"}), 400
    scanner_id = scanner_id.strip()
    if scanner_id not in ble_config.KNOWN_SCANNER_IDS:
        return jsonify({"error": f"Unknown scanner_id: {scanner_id}"}), 400

    device_id = _valid_device_id(data.get("device_id", data.get("tag_id")))
    if device_id is None:
        return jsonify({"error": "device_id must contain only letters, numbers, ':._-' (max 64)"}), 400

    rssi = data.get("rssi")
    if isinstance(rssi, bool) or not isinstance(rssi, int):
        return jsonify({"error": "rssi must be an integer"}), 400
    if not -120 <= rssi <= 0:
        return jsonify({"error": "rssi must be between -120 and 0"}), 400

    tx_power = data.get("tx_power")
    if tx_power is not None and (isinstance(tx_power, bool) or not isinstance(tx_power, int)):
        return jsonify({"error": "tx_power must be an integer or null"}), 400

    device_name = data.get("device_name")
    if device_name is not None:
        if not isinstance(device_name, str) or not device_name.strip() or len(device_name.strip()) > 100:
            return jsonify({"error": "device_name must be a non-empty string of at most 100 characters"}), 400
        device_name = device_name.strip()

    device_address = data.get("device_address")
    if device_address is not None:
        if not isinstance(device_address, str) or not device_address.strip() or len(device_address.strip()) > 100:
            return jsonify({"error": "device_address must be a non-empty string of at most 100 characters"}), 400
        device_address = device_address.strip()

    try:
        received_at = insert_bluetooth_reading(
            scanner_id=scanner_id,
            tag_id=device_id,
            rssi=rssi,
            tx_power=tx_power,
        )
        ble_service.register_device_metadata(
            device_id,
            device_name=device_name,
            device_address=device_address,
        )
    except Exception:
        return jsonify({"error": "Database error"}), 500

    return jsonify({
        "success": True,
        "message": "Bluetooth device reading recorded",
        "data": {
            "scanner_id": scanner_id,
            "device_id": device_id,
            "tag_id": device_id,
            "device_name": device_name,
            "rssi": rssi,
            "received_at": received_at,
        },
    }), 201


def _state_response(device_id: str):
    valid_id = _valid_device_id(device_id)
    if valid_id is None:
        return jsonify({"error": "Invalid Bluetooth device ID"}), 400
    return jsonify(ble_service.get_device_state(valid_id)), 200


@ble_api.get("/state/<device_id>")
def get_state(device_id: str):
    return _state_response(device_id)


@ble_api.get("/position/<device_id>")
def get_position(device_id: str):
    """Backward-compatible path; the response contains no coordinates."""
    return _state_response(device_id)


@ble_api.get("/devices")
def list_devices():
    return jsonify(ble_service.get_tracking_summary()), 200


@ble_api.get("/tags")
def list_tags():
    """Backward-compatible alias for /devices."""
    return jsonify(ble_service.get_tracking_summary()), 200


@ble_api.get("/count")
def get_count():
    summary = ble_service.get_tracking_summary()
    left_count = summary["zones"]["left"]["count"]
    right_count = summary["zones"]["right"]["count"]
    return jsonify({
        "total_active_devices": summary["total_active_devices"],
        "total_active_tags": summary["total_active_tags"],
        "max_devices": summary["max_devices"],
        "zones": summary["zones"],
        "unassigned_count": summary["total_active_devices"] - left_count - right_count,
        "ignored_active_devices": summary["ignored_active_devices"],
        "inactive_timeout_seconds": ble_config.BLE_SETTINGS["inactive_timeout_seconds"],
    }), 200
