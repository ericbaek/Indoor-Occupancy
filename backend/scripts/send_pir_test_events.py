"""
send_pir_test_events.py
=======================
Sends a realistic sequence of PIR doorway occupancy events to the backend
without needing the real hardware.

Usage (from the backend/ directory with the virtual environment active):

    python scripts/send_pir_test_events.py

The backend must already be running:

    python run.py

Expected final occupancy:  2
  event_id 1  entry  → +1 → 1
  event_id 2  entry  → +1 → 2
  event_id 3  entry  → +1 → 3
  event_id 4  exit   → -1 → 2
  event_id 5  entry  → +1 → 3
  event_id 6  exit   → -1 → 2
"""

import json
import sys
import urllib.error
import urllib.request

BASE_URL = "http://localhost:5000"
ENDPOINT = f"{BASE_URL}/api/occupancy/events"
CURRENT_URL = f"{BASE_URL}/api/occupancy/current"
DEVICE_ID = "doorway-pico-01"

# ---------------------------------------------------------------------------
# Simulated hardware events
# ---------------------------------------------------------------------------

EVENTS = [
    {
        "device_id": DEVICE_ID,
        "event_id": 1,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 2404,
        "uptime_ms": 508384,
    },
    {
        "device_id": DEVICE_ID,
        "event_id": 2,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 1870,
        "uptime_ms": 513000,
    },
    {
        "device_id": DEVICE_ID,
        "event_id": 3,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 3100,
        "uptime_ms": 519500,
    },
    {
        "device_id": DEVICE_ID,
        "event_id": 4,
        "event": "exit",
        "count_change": -1,
        "duration_ms": 1222,
        "uptime_ms": 525000,
    },
    {
        "device_id": DEVICE_ID,
        "event_id": 5,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 2050,
        "uptime_ms": 530200,
    },
    {
        "device_id": DEVICE_ID,
        "event_id": 6,
        "event": "exit",
        "count_change": -1,
        "duration_ms": 980,
        "uptime_ms": 536700,
    },
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def post_json(url: str, payload: dict) -> tuple[int, dict]:
    """Send a JSON POST request and return (status_code, response_body)."""
    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read())


def get_json(url: str) -> tuple[int, dict]:
    """Send a GET request and return (status_code, response_body)."""
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=" * 60)
    print("  PIR Doorway Occupancy — Test Event Sender")
    print(f"  Endpoint: {ENDPOINT}")
    print("=" * 60)

    # Verify the backend is reachable before sending events.
    get_json(f"{BASE_URL}/api/health")

    for event in EVENTS:
        status, body = post_json(ENDPOINT, event)
        label = f"  event_id={event['event_id']}  {event['event']}"
        if status == 201:
            print(f"{label}  →  OK (201)")
        elif status == 409:
            print(f"{label}  →  DUPLICATE, already stored (409)")
        else:
            print(f"{label}  →  ERROR {status}: {body.get('error', body)}")

    # Fetch and display the current occupancy.
    print("-" * 60)
    status, body = get_json(CURRENT_URL)
    if status == 200:
        print(f"  Current occupancy : {body['occupancy']}")
        print(f"  Updated at        : {body['updated_at']}")
    else:
        print(f"  [ERROR] Could not fetch occupancy: {status} {body}")

    print("=" * 60)
    print("  Expected final occupancy: 2")
    print("=" * 60)


if __name__ == "__main__":
    main()
