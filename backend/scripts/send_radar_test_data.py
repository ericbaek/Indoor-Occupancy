"""
send_radar_test_data.py
=======================
Sends test payloads to the Flask backend without needing real hardware.
Covers radar readings, occupancy events, and intentionally invalid inputs.

Usage (from the backend/ directory with the virtual environment active):

    python scripts/send_radar_test_data.py

The backend must already be running:

    python run.py

Override the backend URL:

    BACKEND_URL=http://192.168.1.10:5000 python scripts/send_radar_test_data.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:5000").rstrip("/")
DEVICE_ID = "test-pico-01"


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def post_json(path: str, payload: dict) -> tuple[int, dict]:
    """Send a JSON POST request; return (status_code, response_body)."""
    url = BASE_URL + path
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url, data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())
    except urllib.error.URLError as exc:
        print(f"\n[ERROR] Cannot connect to backend at {BASE_URL}")
        print(f"        Reason: {exc.reason}")
        print("        Make sure the backend is running: python run.py")
        sys.exit(1)


def get_json(path: str) -> tuple[int, dict]:
    """Send a GET request; return (status_code, response_body)."""
    url = BASE_URL + path
    try:
        with urllib.request.urlopen(url) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())
    except urllib.error.URLError as exc:
        print(f"\n[ERROR] Cannot connect to backend at {BASE_URL}")
        print(f"        Reason: {exc.reason}")
        print("        Make sure the backend is running: python run.py")
        sys.exit(1)


def _print_result(label: str, status: int, body: dict) -> None:
    ok = "✓" if status in (200, 201) else "✗"
    print(f"  {ok}  [{status}]  {label}")
    if status not in (200, 201):
        print(f"          {body.get('error', body)}")


# ---------------------------------------------------------------------------
# Test scenarios
# ---------------------------------------------------------------------------

def _radar_section() -> None:
    print("\n── Radar readings (POST /api/radar/readings) ──────────────────")

    # 0 targets
    status, body = post_json("/api/radar/readings", {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": 1000,
        "target_count": 0,
        "targets": [],
    })
    _print_result("radar — 0 targets", status, body)

    # 1 target
    status, body = post_json("/api/radar/readings", {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": 2000,
        "target_count": 1,
        "targets": [
            {"target_id": 1, "x_mm": 420, "y_mm": 1350,
             "distance_mm": 1413.8, "angle_deg": 17.3, "speed_cm_s": -25},
        ],
    })
    _print_result("radar — 1 target", status, body)

    # 3 targets
    status, body = post_json("/api/radar/readings", {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": 3000,
        "target_count": 3,
        "targets": [
            {"target_id": 1, "x_mm": 100, "y_mm": 500,
             "distance_mm": 510.0, "angle_deg": 11.3, "speed_cm_s": 0},
            {"target_id": 2, "x_mm": -200, "y_mm": 800,
             "distance_mm": 824.6, "angle_deg": -14.0, "speed_cm_s": 5},
            {"target_id": 3, "x_mm": 50, "y_mm": 1200,
             "distance_mm": 1201.0, "angle_deg": 2.4, "speed_cm_s": -10},
        ],
    })
    _print_result("radar — 3 targets", status, body)

    # Invalid: target_count = 4 (should be rejected)
    status, body = post_json("/api/radar/readings", {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": 4000,
        "target_count": 4,
        "targets": [],
    })
    _print_result("radar — target_count=4 (expect 400)", status, body)

    # Invalid: message_type wrong (should be rejected)
    status, body = post_json("/api/radar/readings", {
        "message_type": "occupancy_event",
        "device_id": DEVICE_ID,
        "uptime_ms": 5000,
        "target_count": 0,
        "targets": [],
    })
    _print_result("radar — wrong message_type (expect 400)", status, body)

    # Invalid: missing required target field
    status, body = post_json("/api/radar/readings", {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": 6000,
        "target_count": 1,
        "targets": [{"target_id": 1, "x_mm": 100}],  # missing fields
    })
    _print_result("radar — incomplete target (expect 400)", status, body)


def _occupancy_section() -> None:
    print("\n── Occupancy events (POST /api/occupancy/events) ──────────────")

    # Entry with radar snapshot
    status, body = post_json("/api/occupancy/events", {
        "message_type": "occupancy_event",
        "device_id": DEVICE_ID,
        "event_id": 1001,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 820,
        "uptime_ms": 16400,
        "radar": {
            "target_count": 1,
            "targets": [
                {"target_id": 1, "x_mm": 420, "y_mm": 1350,
                 "distance_mm": 1413.8, "angle_deg": 17.3, "speed_cm_s": -25},
            ],
        },
    })
    _print_result("occupancy — entry with radar snapshot", status, body)

    # Exit with empty radar
    status, body = post_json("/api/occupancy/events", {
        "message_type": "occupancy_event",
        "device_id": DEVICE_ID,
        "event_id": 1002,
        "event": "exit",
        "count_change": -1,
        "duration_ms": 600,
        "uptime_ms": 20000,
        "radar": {"target_count": 0, "targets": []},
    })
    _print_result("occupancy — exit with empty radar", status, body)

    # Backward-compatible format (no message_type or radar)
    status, body = post_json("/api/occupancy/events", {
        "device_id": DEVICE_ID,
        "event_id": 1003,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 1000,
        "uptime_ms": 25000,
    })
    _print_result("occupancy — entry without message_type/radar (backward compat)", status, body)

    # Invalid: wrong message_type
    status, body = post_json("/api/occupancy/events", {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "event_id": 1004,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 500,
        "uptime_ms": 30000,
    })
    _print_result("occupancy — wrong message_type (expect 400)", status, body)

    # Invalid: radar target_count mismatch
    status, body = post_json("/api/occupancy/events", {
        "message_type": "occupancy_event",
        "device_id": DEVICE_ID,
        "event_id": 1005,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 500,
        "uptime_ms": 35000,
        "radar": {"target_count": 2, "targets": []},
    })
    _print_result("occupancy — radar count/targets mismatch (expect 400)", status, body)


def _query_section() -> None:
    print("\n── Query endpoints ─────────────────────────────────────────────")

    status, body = get_json("/api/radar/latest")
    _print_result("GET /api/radar/latest", status, body)

    status, body = get_json(f"/api/radar/latest/{DEVICE_ID}")
    _print_result(f"GET /api/radar/latest/{DEVICE_ID}", status, body)

    status, body = get_json("/api/radar/latest/nonexistent-device")
    _print_result("GET /api/radar/latest/nonexistent (expect 404)", status, body)

    status, body = get_json("/api/occupancy/current")
    _print_result("GET /api/occupancy/current", status, body)
    if status == 200:
        print(f"          occupancy = {body.get('occupancy')}")

    status, body = get_json("/api/occupancy/status")
    _print_result("GET /api/occupancy/status", status, body)
    if status == 200:
        print(f"          status = {body.get('status')!r},  "
              f"radar_target_count = {body.get('radar_target_count')}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  Radar + Occupancy Test Data Sender")
    print(f"  Backend: {BASE_URL}")
    print("=" * 60)

    # Verify the backend is reachable.
    get_json("/api/health")

    _radar_section()
    _occupancy_section()
    _query_section()

    print("\n" + "=" * 60)
    print("  Done.")
    print("=" * 60)


if __name__ == "__main__":
    main()
