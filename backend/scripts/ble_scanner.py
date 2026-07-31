"""
ble_scanner.py
==============
Bluetooth Low Energy scanner for Windows laptops acting as tracking anchors.

Uses `bleak` for non-blocking BLE scanning and `requests` for pushing readings
to the Flask backend.

Usage:
    $env:SCANNER_ID="anchor-left"
    $env:BACKEND_URL="http://192.168.1.20:5000/api/bluetooth/readings"
    python scripts/ble_scanner.py
"""

import asyncio
import json
import logging
import os
import sys
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

# Configuration
SCANNER_ID = os.environ.get("SCANNER_ID")
BACKEND_URL = os.environ.get("BACKEND_URL")

# Rate limiting minimum interval per tag (seconds)
MIN_SEND_INTERVAL = 0.5
last_send_times: dict[str, float] = {}


async def sender_task(queue: asyncio.Queue):
    """Asynchronous worker that takes readings from the queue and sends them."""
    loop = asyncio.get_running_loop()
    
    while True:
        try:
            reading = await queue.get()
            
            # Send using run_in_executor to avoid blocking the asyncio loop
            # with synchronous requests.post
            await loop.run_in_executor(None, _post_reading, reading)
            
            queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            log.error(f"Sender worker error: {e}")


def _post_reading(reading: dict[str, Any]):
    """Synchronous HTTP POST logic."""
    try:
        resp = requests.post(BACKEND_URL, json=reading, timeout=3.0)
        if not resp.ok:
            log.warning(f"Backend rejected reading: {resp.status_code} - {resp.text}")
    except requests.exceptions.ConnectionError:
        log.error(f"Cannot connect to backend at {BACKEND_URL}")
    except requests.exceptions.Timeout:
        log.warning(f"Timeout sending reading to {BACKEND_URL}")
    except Exception as e:
        log.error(f"HTTP request failed: {e}")


def detection_callback(device: BLEDevice, advertisement_data: AdvertisementData, queue: asyncio.Queue):
    """Called by bleak whenever a BLE advertisement is detected."""
    name = advertisement_data.local_name or device.name or ""
    
    # Fast filtering
    if not name.startswith("ROOM-TAG-"):
        return

    # Check rate limit
    import time
    now = time.time()
    last_time = last_send_times.get(name, 0.0)
    if now - last_time < MIN_SEND_INTERVAL:
        return
        
    last_send_times[name] = now
    
    # Get Tx Power if available
    tx_power = advertisement_data.tx_power
    
    reading = {
        "message_type": "bluetooth_rssi",
        "scanner_id": SCANNER_ID,
        "tag_id": name,
        "rssi": advertisement_data.rssi,
        "tx_power": tx_power,
    }
    
    # Try to put in queue without blocking
    try:
        queue.put_nowait(reading)
        log.info(f"Detected {name}: RSSI={advertisement_data.rssi} dBm")
    except asyncio.QueueFull:
        log.warning("Queue full, dropping reading")


async def main():
    if not SCANNER_ID:
        log.error("SCANNER_ID environment variable must be set (e.g. 'anchor-left')")
        sys.exit(1)
        
    if not BACKEND_URL:
        log.error("BACKEND_URL environment variable must be set")
        sys.exit(1)
        
    log.info(f"Starting BLE scanner '{SCANNER_ID}'")
    log.info(f"Forwarding readings to {BACKEND_URL}")

    # Bounded queue to prevent memory growth if backend is down
    queue = asyncio.Queue(maxsize=50)
    
    # Start the sender task
    sender = asyncio.create_task(sender_task(queue))
    
    # Setup scanner
    scanner = BleakScanner(
        detection_callback=lambda d, a: detection_callback(d, a, queue)
    )
    
    try:
        await scanner.start()
        log.info("Scanner started. Waiting for ROOM-TAG-* devices...")
        
        # Keep the main task alive
        while True:
            await asyncio.sleep(1.0)
            
    except asyncio.CancelledError:
        log.info("Shutting down scanner...")
    finally:
        await scanner.stop()
        sender.cancel()
        log.info("Shutdown complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
