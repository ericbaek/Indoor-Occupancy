"""Windows BLE anchor scanner for up to five participating devices.

Supported participating devices:
1. Windows PCs running ``ble_advertiser_windows.py`` (stable manufacturer ID).
2. Existing Arduino tags advertising a ``ROOM-TAG-*`` local name.
3. Explicitly allowlisted BLE addresses or names via ``BLE_TARGETS``.

Use ``BLE_DISCOVERY=1`` to list nearby advertisers without posting readings.
``BLE_SCAN_ALL=1`` is available for controlled rooms, but an allowlist is more
stable because unrelated watches, earbuds, and rotating private addresses may
otherwise be counted.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import sys
import time
from typing import Any

try:
    from bleak import BleakScanner
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
except ImportError:
    print("Error: 'bleak' is not installed. Run: pip install bleak", file=sys.stderr)
    sys.exit(1)

import requests


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ble_scanner")

SCANNER_ID = os.environ.get("SCANNER_ID")
BACKEND_URL = os.environ.get("BACKEND_URL")
DISCOVERY_ONLY = os.environ.get("BLE_DISCOVERY", "0") == "1"
SCAN_ALL = os.environ.get("BLE_SCAN_ALL", "0") == "1"
TARGET_SELECTORS = {
    value.strip().casefold()
    for value in os.environ.get("BLE_TARGETS", "").split(",")
    if value.strip()
}

COMP6733_COMPANY_ID = 0xFFFE
COMP6733_PAYLOAD_PREFIX = b"C6733:"
DEVICE_TOKEN_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,15}$")
MIN_SEND_INTERVAL = 0.5
DISCOVERY_LOG_INTERVAL = 5.0

last_send_times: dict[str, float] = {}
last_discovery_logs: dict[str, float] = {}


def normalise_address(address: str) -> str:
    return address.strip().upper().replace("_", ":")


def parse_comp6733_device_id(manufacturer_data: dict[int, bytes]) -> str | None:
    """Extract a stable PC identifier from the COMP6733 manufacturer payload."""
    payload = manufacturer_data.get(COMP6733_COMPANY_ID)
    if not payload or not payload.startswith(COMP6733_PAYLOAD_PREFIX):
        return None
    try:
        token = payload[len(COMP6733_PAYLOAD_PREFIX):].decode("ascii").upper()
    except UnicodeDecodeError:
        return None
    if not DEVICE_TOKEN_PATTERN.fullmatch(token):
        return None
    return f"BT-PC-{token}"


def _address_device_id(address: str) -> str:
    # A short hash keeps device addresses out of the UI while preserving a
    # common identity when both anchors observe the same address.
    digest = hashlib.sha256(normalise_address(address).encode("utf-8")).hexdigest()
    return f"BT-ADDR-{digest[:12].upper()}"


def identify_device(
    device: BLEDevice,
    advertisement_data: AdvertisementData,
) -> dict[str, str] | None:
    """Return the canonical participating-device identity, or ``None``."""
    address = normalise_address(device.address)
    name = (advertisement_data.local_name or device.name or "").strip()

    project_device_id = parse_comp6733_device_id(advertisement_data.manufacturer_data)
    if project_device_id:
        token = project_device_id.removeprefix("BT-PC-")
        return {
            "device_id": project_device_id,
            "device_name": name or f"Bluetooth PC {token}",
            "device_address": address,
        }

    if name.upper().startswith("ROOM-TAG-"):
        return {
            "device_id": name.upper(),
            "device_name": name,
            "device_address": address,
        }

    selected = (
        address.casefold() in TARGET_SELECTORS
        or name.casefold() in TARGET_SELECTORS
        or SCAN_ALL
    )
    if not selected:
        return None

    return {
        "device_id": _address_device_id(address),
        "device_name": name or "Unnamed BLE device",
        "device_address": address,
    }


def _post_reading(reading: dict[str, Any]) -> None:
    try:
        response = requests.post(BACKEND_URL, json=reading, timeout=3.0)
        if not response.ok:
            log.warning(
                "Backend rejected reading: %s - %s",
                response.status_code,
                response.text,
            )
    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to backend at %s", BACKEND_URL)
    except requests.exceptions.Timeout:
        log.warning("Timeout sending reading to %s", BACKEND_URL)
    except Exception as exc:  # pragma: no cover - defensive logging
        log.error("HTTP request failed: %s", exc)


async def sender_task(queue: asyncio.Queue) -> None:
    loop = asyncio.get_running_loop()
    while True:
        try:
            reading = await queue.get()
            await loop.run_in_executor(None, _post_reading, reading)
            queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as exc:  # pragma: no cover - defensive logging
            log.error("Sender worker error: %s", exc)


def detection_callback(
    device: BLEDevice,
    advertisement_data: AdvertisementData,
    queue: asyncio.Queue,
) -> None:
    name = (advertisement_data.local_name or device.name or "Unnamed").strip()
    address = normalise_address(device.address)
    now = time.time()

    if DISCOVERY_ONLY:
        discovery_key = f"{address}|{name}"
        if now - last_discovery_logs.get(discovery_key, 0.0) >= DISCOVERY_LOG_INTERVAL:
            last_discovery_logs[discovery_key] = now
            log.info(
                "DISCOVERED name=%r address=%s RSSI=%s manufacturer_ids=%s",
                name,
                address,
                advertisement_data.rssi,
                sorted(advertisement_data.manufacturer_data),
            )
        return

    identity = identify_device(device, advertisement_data)
    if identity is None:
        return

    device_id = identity["device_id"]
    if now - last_send_times.get(device_id, 0.0) < MIN_SEND_INTERVAL:
        return
    last_send_times[device_id] = now

    reading = {
        "message_type": "bluetooth_rssi",
        "scanner_id": SCANNER_ID,
        **identity,
        "rssi": advertisement_data.rssi,
        "tx_power": advertisement_data.tx_power,
    }
    try:
        queue.put_nowait(reading)
        log.info(
            "Detected %s (%s): RSSI=%s dBm",
            identity["device_name"],
            device_id,
            advertisement_data.rssi,
        )
    except asyncio.QueueFull:
        log.warning("Queue full, dropping reading")


async def main() -> None:
    if not DISCOVERY_ONLY and not SCANNER_ID:
        log.error("SCANNER_ID must be anchor-left or anchor-right")
        sys.exit(1)
    if not DISCOVERY_ONLY and not BACKEND_URL:
        log.error("BACKEND_URL environment variable must be set")
        sys.exit(1)

    if DISCOVERY_ONLY:
        log.info("Starting BLE discovery mode (no readings will be posted)")
    else:
        log.info("Starting BLE scanner %r", SCANNER_ID)
        log.info("Forwarding readings to %s", BACKEND_URL)
        if TARGET_SELECTORS:
            log.info("Allowlisted targets: %s", sorted(TARGET_SELECTORS))
        elif SCAN_ALL:
            log.warning("BLE_SCAN_ALL=1: unrelated nearby BLE advertisers may be counted")
        else:
            log.info("Accepting COMP6733 PC beacons and ROOM-TAG-* devices")

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    sender = asyncio.create_task(sender_task(queue))
    scanner = BleakScanner(
        detection_callback=lambda device, data: detection_callback(device, data, queue)
    )

    try:
        await scanner.start()
        log.info("Scanner started")
        while True:
            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        log.info("Shutting down scanner")
    finally:
        await scanner.stop()
        sender.cancel()
        log.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
