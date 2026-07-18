"""
send_environment_test_data.py
=============================
Send simulated CO2 / environment sensor readings to the backend and query
the resulting state.  Mirrors the pattern of send_radar_test_data.py.

Usage
-----
    # Backend must be running first:
    python run.py

    # In a separate terminal (from the backend/ directory):
    python scripts/send_environment_test_data.py

    # Override the backend URL:
    python scripts/send_environment_test_data.py --url http://192.168.1.10:5000
"""

import argparse
import json
import os
import sys
import time

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_URL = os.environ.get("BACKEND_URL", "http://localhost:5000")
DEVICE = "scd41-nano-01"

# ---------------------------------------------------------------------------
# Test payloads
# ---------------------------------------------------------------------------

# Simulate a sequence of CO2 readings that increase as people enter a room.
_TEST_READINGS = [
    {
        "label": "Empty room — baseline CO2",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 1000,
            "co2_ppm": 420,
            "temperature_c": 21.0,
            "humidity_percent": 45.0,
        },
        "expect_status": 201,
    },
    {
        "label": "1 person entered — CO2 rising",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 6000,
            "co2_ppm": 650,
            "temperature_c": 21.5,
            "humidity_percent": 48.0,
        },
        "expect_status": 201,
    },
    {
        "label": "Several people — elevated CO2",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 11000,
            "co2_ppm": 1100,
            "temperature_c": 22.3,
            "humidity_percent": 55.0,
        },
        "expect_status": 201,
    },
    {
        "label": "Crowded room — high CO2",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 16000,
            "co2_ppm": 2300,
            "temperature_c": 23.5,
            "humidity_percent": 68.0,
        },
        "expect_status": 201,
    },
    {
        "label": "Room clearing — CO2 dropping",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 21000,
            "co2_ppm": 900,
            "temperature_c": 22.0,
            "humidity_percent": 52.0,
        },
        "expect_status": 201,
    },
    # --- Invalid payloads (should be rejected) ---
    {
        "label": "INVALID: wrong message_type",
        "payload": {
            "message_type": "radar",
            "device_id": DEVICE,
            "uptime_ms": 26000,
            "co2_ppm": 500,
            "temperature_c": 21.0,
            "humidity_percent": 50.0,
        },
        "expect_status": 400,
    },
    {
        "label": "INVALID: missing co2_ppm",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 31000,
            "temperature_c": 21.0,
            "humidity_percent": 50.0,
        },
        "expect_status": 400,
    },
    {
        "label": "INVALID: humidity > 100",
        "payload": {
            "message_type": "environment",
            "device_id": DEVICE,
            "uptime_ms": 36000,
            "co2_ppm": 500,
            "temperature_c": 21.0,
            "humidity_percent": 150.0,
        },
        "expect_status": 400,
    },
    # --- Second device ---
    {
        "label": "Second device — scd41-nano-02",
        "payload": {
            "message_type": "environment",
            "device_id": "scd41-nano-02",
            "uptime_ms": 5000,
            "co2_ppm": 780,
            "temperature_c": 20.5,
            "humidity_percent": 42.0,
        },
        "expect_status": 201,
    },
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _post(url: str, payload: dict) -> requests.Response:
    return requests.post(url, json=payload, timeout=5)


def _get(url: str) -> requests.Response:
    return requests.get(url, timeout=5)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Send test environment / CO2 sensor data to the backend."
    )
    parser.add_argument(
        "--url", default=DEFAULT_URL,
        help=f"Backend base URL (default: {DEFAULT_URL})",
    )
    args = parser.parse_args()
    base = args.url.rstrip("/")
    post_url = f"{base}/api/co2/readings"

    print("=" * 60)
    print(f"  CO2 / Environment — Test Data Sender")
    print(f"  Endpoint: {post_url}")
    print("=" * 60)

    all_ok = True
    for item in _TEST_READINGS:
        label = item["label"]
        payload = item["payload"]
        expect = item["expect_status"]

        try:
            resp = _post(post_url, payload)
            status = resp.status_code
            ok = status == expect
            marker = "OK" if ok else "FAIL"
            print(f"  {label:<45s}  →  {marker} ({status})")
            if not ok:
                all_ok = False
                print(f"    Expected {expect}, got {status}: {resp.text[:120]}")
        except requests.exceptions.ConnectionError:
            print(f"  {label:<45s}  →  CONNECTION ERROR")
            all_ok = False

    print("-" * 60)

    # --- Query latest for all devices ---
    print("\n  GET /api/co2/latest")
    try:
        resp = _get(f"{base}/api/co2/latest")
        data = resp.get_json() if hasattr(resp, "get_json") else resp.json()
        for dev in data.get("devices", []):
            print(f"    {dev['device_id']}: CO2={dev['co2_ppm']}ppm  "
                  f"T={dev['temperature_c']}°C  H={dev['humidity_percent']}%")
    except Exception as exc:
        print(f"    Error: {exc}")

    # --- Query latest for primary device ---
    print(f"\n  GET /api/co2/latest/{DEVICE}")
    try:
        resp = _get(f"{base}/api/co2/latest/{DEVICE}")
        data = resp.get_json() if hasattr(resp, "get_json") else resp.json()
        print(f"    CO2: {data.get('co2_ppm')} ppm")
        print(f"    Temperature: {data.get('temperature_c')} °C")
        print(f"    Humidity: {data.get('humidity_percent')} %")
    except Exception as exc:
        print(f"    Error: {exc}")

    # --- Query history ---
    print(f"\n  GET /api/co2/history/{DEVICE}?limit=5")
    try:
        resp = _get(f"{base}/api/co2/history/{DEVICE}?limit=5")
        data = resp.get_json() if hasattr(resp, "get_json") else resp.json()
        readings = data.get("readings", [])
        print(f"    {len(readings)} reading(s) returned")
        for r in readings[:3]:
            print(f"    CO2={r['co2_ppm']}ppm  T={r['temperature_c']}°C  "
                  f"H={r['humidity_percent']}%  at {r['received_at']}")
    except Exception as exc:
        print(f"    Error: {exc}")

    # --- Query unified status ---
    print(f"\n  GET /api/occupancy/status")
    try:
        resp = _get(f"{base}/api/occupancy/status")
        data = resp.get_json() if hasattr(resp, "get_json") else resp.json()
        print(f"    Occupancy: {data.get('occupancy')}")
        print(f"    Status: {data.get('status')}")
        print(f"    CO2: {data.get('co2_ppm')} ppm ({data.get('co2_level')})")
        print(f"    Temperature: {data.get('temperature_c')} °C")
        print(f"    Humidity: {data.get('humidity_percent')} %")
    except Exception as exc:
        print(f"    Error: {exc}")

    print("\n" + "=" * 60)
    if all_ok:
        print("  All test cases passed!")
    else:
        print("  Some test cases FAILED — see above for details.")
    print("=" * 60)


if __name__ == "__main__":
    main()
