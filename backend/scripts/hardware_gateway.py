"""
hardware_gateway.py
===================
Reads JSON lines from stdin or a serial port and forwards them to the
Flask backend via HTTP POST.

Supported message types:
  - "radar"           → POST /api/radar/readings
  - "occupancy_event" → POST /api/occupancy/events
  - "environment"     → POST /api/environment/readings

Usage
-----
Stdin mode (pipe hardware output or simulate with echo):

    python scripts/hardware_gateway.py --mode stdin

    echo '{"message_type":"radar","device_id":"doorway-pico-01","uptime_ms":1000,"target_count":0,"targets":[]}' \\
        | python scripts/hardware_gateway.py --mode stdin

Serial mode (connect the Raspberry Pi Pico via USB):

    python scripts/hardware_gateway.py --mode serial --port /dev/ttyACM0 --baudrate 115200

    # On Windows the port is typically COM3, COM4, etc.
    python scripts/hardware_gateway.py --mode serial --port COM3 --baudrate 115200

Backend URL
-----------
Override the default backend URL via --url or the BACKEND_URL environment
variable:

    BACKEND_URL=http://192.168.1.10:5000 python scripts/hardware_gateway.py --mode stdin

Notes
-----
- The Pico's internal UART to the RD03D radar uses 256 000 baud, but the
  USB CDC serial port presented to the host PC always runs at 115 200 baud.
- Bad JSON lines are logged and skipped without crashing.
- Unknown message types are logged and skipped.
- HTTP errors and connection failures are logged; the gateway keeps running.
"""

import argparse
import json
import logging
import os
import sys

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("hardware_gateway")

# ---------------------------------------------------------------------------
# Endpoint routing
# ---------------------------------------------------------------------------

_ROUTES: dict[str, str] = {
    "radar": "/api/radar/readings",
    "occupancy_event": "/api/occupancy/events",
    "environment": "/api/environment/readings",
}

HTTP_TIMEOUT = 5  # seconds


def _forward(base_url: str, message: dict) -> None:
    """Forward a parsed message to the appropriate backend endpoint."""
    message_type = message.get("message_type", "")
    path = _ROUTES.get(message_type)

    if path is None:
        log.warning("Unknown message_type %r — skipping", message_type)
        return

    url = base_url.rstrip("/") + path
    try:
        resp = requests.post(url, json=message, timeout=HTTP_TIMEOUT)
        if resp.ok:
            log.info("POST %s → %d %s", path, resp.status_code, resp.text[:120])
        else:
            log.warning(
                "POST %s returned %d: %s", path, resp.status_code, resp.text[:200]
            )
    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to backend at %s — is the server running?", base_url)
    except requests.exceptions.Timeout:
        log.error("Request to %s timed out after %ds", url, HTTP_TIMEOUT)
    except requests.exceptions.RequestException as exc:
        log.error("HTTP request failed: %s", exc)


# ---------------------------------------------------------------------------
# Line processing
# ---------------------------------------------------------------------------

def _process_line(line: str, base_url: str) -> None:
    """Parse a single JSON line and forward it to the backend."""
    line = line.strip()
    if not line:
        return

    try:
        message = json.loads(line)
    except json.JSONDecodeError as exc:
        log.warning("Invalid JSON (skipping): %s — raw: %r", exc, line[:120])
        return

    if not isinstance(message, dict):
        log.warning("Expected a JSON object, got %s — skipping", type(message).__name__)
        return

    _forward(base_url, message)


# ---------------------------------------------------------------------------
# Input sources
# ---------------------------------------------------------------------------

def _run_stdin(base_url: str) -> None:
    """Read JSON lines from stdin until EOF."""
    log.info("Listening on stdin (Ctrl-D / Ctrl-Z to stop)")
    for raw_line in sys.stdin:
        _process_line(raw_line, base_url)


def _run_serial(port: str, baudrate: int, base_url: str) -> None:
    """Read JSON lines from a serial port indefinitely."""
    try:
        import serial  # type: ignore[import-untyped]
    except ImportError:
        log.error(
            "pyserial is not installed.  Run: pip install pyserial"
        )
        sys.exit(1)

    log.info("Opening serial port %s at %d baud", port, baudrate)
    try:
        ser = serial.Serial(port, baudrate=baudrate, timeout=1)
    except serial.SerialException as exc:
        log.error("Cannot open serial port %s: %s", port, exc)
        sys.exit(1)

    log.info("Connected to %s.  Forwarding to %s", port, base_url)
    buffer = ""
    try:
        while True:
            try:
                chunk = ser.readline().decode("utf-8", errors="replace")
                buffer += chunk
                # readline() includes '\n'; process complete lines.
                if "\n" in buffer:
                    lines = buffer.split("\n")
                    for line in lines[:-1]:
                        _process_line(line, base_url)
                    buffer = lines[-1]
            except serial.SerialException as exc:
                log.error("Serial read error: %s — retrying", exc)
    except KeyboardInterrupt:
        log.info("Interrupted.  Closing serial port.")
    finally:
        ser.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def _parse_args() -> argparse.Namespace:
    default_url = os.environ.get("BACKEND_URL", "http://localhost:5000")

    parser = argparse.ArgumentParser(
        description="Hardware gateway: forward Pico JSON output to the Flask backend."
    )
    parser.add_argument(
        "--mode",
        choices=["stdin", "serial"],
        default="stdin",
        help="Input source (default: stdin)",
    )
    parser.add_argument(
        "--port",
        default=None,
        help="Serial port device, e.g. /dev/ttyACM0 or COM3 (required for serial mode)",
    )
    parser.add_argument(
        "--baudrate",
        type=int,
        default=115200,
        help="Serial baud rate (default: 115200 — Pico USB CDC)",
    )
    parser.add_argument(
        "--url",
        default=default_url,
        help=f"Backend base URL (default: {default_url}; or set BACKEND_URL env var)",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    log.info("Backend URL: %s", args.url)

    if args.mode == "stdin":
        _run_stdin(args.url)
    elif args.mode == "serial":
        if args.port is None:
            log.error("--port is required for serial mode")
            sys.exit(1)
        _run_serial(args.port, args.baudrate, args.url)


if __name__ == "__main__":
    main()
