"""Flask endpoints for the two-zone Bluetooth signal-strength heatmap."""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, request

from . import ble_config, ble_service


ble_api = Blueprint("ble_api", __name__, url_prefix="/api/bluetooth")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _post_signal():
    if not request.is_json:
        return jsonify({"error": "Request body must be JSON"}), 400
    data = request.get_json(silent=True)
    if data is None:
        return jsonify({"error": "Invalid or empty JSON body"}), 400

    anchor_id = data.get("anchor_id")
    if not isinstance(anchor_id, str) or anchor_id not in ble_config.KNOWN_ANCHOR_IDS:
        expected = ", ".join(sorted(ble_config.KNOWN_ANCHOR_IDS))
        return jsonify({"error": f"anchor_id must be one of: {expected}"}), 400

    if "average_rssi" not in data:
        return jsonify({"error": "average_rssi is required"}), 400
    average_rssi = data["average_rssi"]
    if average_rssi is not None:
        if not _is_number(average_rssi):
            return jsonify({"error": "average_rssi must be a number or null"}), 400
        average_rssi = float(average_rssi)
        if not -120 <= average_rssi <= 0:
            return jsonify({"error": "average_rssi must be between -120 and 0"}), 400

    signal_score = data.get("signal_score")
    if not _is_number(signal_score):
        return jsonify({"error": "signal_score must be a number"}), 400
    signal_score = float(signal_score)
    if not 0 <= signal_score <= 100:
        return jsonify({"error": "signal_score must be between 0 and 100"}), 400
    if average_rssi is None and signal_score != 0:
        return jsonify({"error": "signal_score must be 0 when average_rssi is null"}), 400

    timestamp = data.get("timestamp")
    if timestamp is not None:
        if not isinstance(timestamp, str) or not timestamp.strip():
            return jsonify({"error": "timestamp must be a non-empty ISO-8601 string"}), 400
        try:
            datetime.fromisoformat(timestamp.strip().replace("Z", "+00:00"))
        except ValueError:
            return jsonify({"error": "timestamp must be a valid ISO-8601 string"}), 400
        timestamp = timestamp.strip()

    snapshot = ble_service.record_anchor_signal(
        anchor_id,
        average_rssi=average_rssi,
        reported_signal_score=signal_score,
        reported_at=timestamp,
    )
    return jsonify({
        "success": True,
        "message": "Bluetooth anchor signal recorded",
        "data": snapshot,
    }), 201


@ble_api.post("/signals")
def post_signal():
    return _post_signal()


@ble_api.post("/readings")
def post_signal_compatibility_alias():
    """Compatibility URL for deployments that already allowlisted /readings."""
    return _post_signal()


@ble_api.get("/signal-strength")
def get_signal_strength():
    return jsonify(ble_service.get_signal_summary()), 200


@ble_api.get("/zones")
def get_zones_alias():
    return jsonify(ble_service.get_signal_summary()), 200
