"""Tests for the two-zone Bluetooth signal-strength heatmap."""

from datetime import datetime, timedelta, timezone

import pytest

from app import ble_config, ble_service


@pytest.fixture(autouse=True)
def clear_ble_anchor_state():
    ble_service.reset_anchor_state()
    yield
    ble_service.reset_anchor_state()


def _payload(**overrides):
    payload = {
        "anchor_id": "left-anchor",
        "average_rssi": -55.0,
        "signal_score": 75.0,
        "timestamp": "2026-08-04T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


def _post(client, **overrides):
    return client.post("/api/bluetooth/signals", json=_payload(**overrides))


def test_anchor_configuration_is_left_and_right():
    assert ble_config.ANCHOR_ZONES == {
        "left-anchor": "left",
        "right-anchor": "right",
    }


@pytest.mark.parametrize(
    ("rssi", "expected"),
    [(-120, 0.0), (-100, 0.0), (-70, 50.0), (-40, 100.0), (-20, 100.0)],
)
def test_rssi_to_score_is_clamped(rssi, expected):
    assert ble_service.rssi_to_score(rssi) == expected


def test_post_anchor_signal(client):
    response = _post(client)
    assert response.status_code == 201
    data = response.get_json()["data"]
    assert data["anchor_id"] == "left-anchor"
    assert data["zone"] == "left"
    assert data["status"] == "active"
    assert data["average_rssi"] == -55.0
    assert data["signal_score"] == 75.0


def test_readings_url_is_signal_payload_alias(client):
    response = client.post("/api/bluetooth/readings", json=_payload())
    assert response.status_code == 201
    assert response.get_json()["data"]["anchor_id"] == "left-anchor"


def test_post_requires_json(client):
    response = client.post("/api/bluetooth/signals", data="not json")
    assert response.status_code == 400
    assert response.get_json()["error"] == "Request body must be JSON"


def test_post_rejects_empty_json(client):
    response = client.post(
        "/api/bluetooth/signals",
        data="",
        content_type="application/json",
    )
    assert response.status_code == 400


@pytest.mark.parametrize("anchor_id", [None, "", "anchor-left", "third-anchor"])
def test_post_rejects_unknown_anchor(client, anchor_id):
    assert _post(client, anchor_id=anchor_id).status_code == 400


@pytest.mark.parametrize("average_rssi", ["-55", True, -121, 1])
def test_post_rejects_invalid_average_rssi(client, average_rssi):
    assert _post(client, average_rssi=average_rssi).status_code == 400


def test_post_requires_average_rssi(client):
    payload = _payload()
    del payload["average_rssi"]
    assert client.post("/api/bluetooth/signals", json=payload).status_code == 400


@pytest.mark.parametrize("signal_score", [None, "75", True, -1, 101])
def test_post_rejects_invalid_signal_score(client, signal_score):
    assert _post(client, signal_score=signal_score).status_code == 400


def test_null_rssi_requires_zero_score(client):
    response = _post(client, average_rssi=None, signal_score=50)
    assert response.status_code == 400


def test_no_advertisements_is_active_zero_signal(client):
    response = _post(client, average_rssi=None, signal_score=0)
    data = response.get_json()["data"]
    assert data["status"] == "active"
    assert data["average_rssi"] is None
    assert data["signal_score"] == 0.0


@pytest.mark.parametrize("timestamp", [12, "", "not-a-timestamp"])
def test_post_rejects_invalid_timestamp(client, timestamp):
    assert _post(client, timestamp=timestamp).status_code == 400


def test_signal_summary_starts_offline(client):
    body = client.get("/api/bluetooth/signal-strength").get_json()
    assert body["measurement"] == "relative_bluetooth_signal_intensity"
    assert body["zones"]["left"]["status"] == "offline"
    assert body["zones"]["right"]["status"] == "offline"
    assert body["stronger_zone"] is None
    assert "total_active_devices" not in body


def test_stronger_zone_uses_signal_score_not_device_count(client):
    _post(client, anchor_id="left-anchor", average_rssi=-50, signal_score=1)
    _post(client, anchor_id="right-anchor", average_rssi=-70, signal_score=99)
    body = client.get("/api/bluetooth/signal-strength").get_json()
    assert body["zones"]["left"]["signal_score"] == 83.33
    assert body["zones"]["right"]["signal_score"] == 50.0
    assert body["stronger_zone"] == "left"


def test_near_equal_scores_are_balanced(client):
    _post(client, anchor_id="left-anchor", average_rssi=-60, signal_score=66.67)
    _post(client, anchor_id="right-anchor", average_rssi=-61, signal_score=65.0)
    body = client.get("/api/bluetooth/signal-strength").get_json()
    assert body["stronger_zone"] == "balanced"


def test_one_active_anchor_does_not_claim_comparison(client):
    _post(client, anchor_id="left-anchor")
    body = client.get("/api/bluetooth/signal-strength").get_json()
    assert body["zones"]["left"]["status"] == "active"
    assert body["zones"]["right"]["status"] == "offline"
    assert body["stronger_zone"] is None


def test_ema_smooths_score(client):
    _post(client, average_rssi=-100, signal_score=0)
    second = _post(client, average_rssi=-40, signal_score=100).get_json()["data"]
    assert second["raw_signal_score"] == 100.0
    assert second["signal_score"] == 30.0


def test_anchor_calibration_offset_is_applied(client, monkeypatch):
    monkeypatch.setitem(ble_config.ANCHOR_RSSI_OFFSET, "right-anchor", 4.0)
    data = _post(
        client,
        anchor_id="right-anchor",
        average_rssi=-70,
        signal_score=50,
    ).get_json()["data"]
    assert data["average_rssi"] == -66.0
    assert data["signal_score"] == 56.67
    assert data["calibration_offset_db"] == 4.0


def test_anchor_becomes_offline_after_timeout(client, monkeypatch):
    base = datetime(2026, 8, 4, tzinfo=timezone.utc)
    monkeypatch.setattr(ble_service, "_utc_now", lambda: base)
    _post(client)
    monkeypatch.setattr(
        ble_service,
        "_utc_now",
        lambda: base + timedelta(seconds=16),
    )
    zone = client.get("/api/bluetooth/signal-strength").get_json()["zones"]["left"]
    assert zone["status"] == "offline"
    assert zone["average_rssi"] is None
    assert zone["signal_score"] is None
    assert zone["last_seen_at"] == base.isoformat()


def test_zones_alias_returns_same_shape(client):
    _post(client)
    body = client.get("/api/bluetooth/zones").get_json()
    assert body["zones"]["left"]["anchor_id"] == "left-anchor"


@pytest.mark.parametrize(
    "path",
    [
        "/api/bluetooth/count",
        "/api/bluetooth/devices",
        "/api/bluetooth/tags",
        "/api/bluetooth/state/BT-01",
        "/api/bluetooth/position/BT-01",
    ],
)
def test_removed_count_and_position_endpoints_return_gone(client, path):
    response = client.get(path)
    assert response.status_code == 410
    assert response.get_json()["use"] == "/api/bluetooth/signal-strength"


def test_occupancy_status_no_longer_exposes_bluetooth_counts(client):
    body = client.get("/api/occupancy/status").get_json()
    assert "bluetooth_device_count" not in body
    assert "bluetooth_tag_count" not in body
    assert "bluetooth_zones" not in body
