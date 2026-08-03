"""Advertise a stable COMP6733 Bluetooth PC identity on Windows.

Run this on every computer that should be counted. Windows reserves the BLE
Local Name field for the operating system, so this script publishes a compact
stable identifier in manufacturer data instead.

An anchor PC cannot receive its own advertisement through the same adapter.
For a PC that is also an anchor, pass ``--co-located-anchor``. The script then
posts a strong self-proximity heartbeat only while the Bluetooth publisher is
successfully running, allowing that PC to be classified on its known side.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import sys
import threading
import time

import requests


COMP6733_COMPANY_ID = 0xFFFE
COMP6733_PAYLOAD_PREFIX = b"C6733:"
DEVICE_TOKEN_PATTERN = re.compile(r"^[A-Z0-9][A-Z0-9-]{0,15}$")
PUBLISHER_STATUS = {
    0: "created",
    1: "waiting",
    2: "started",
    3: "stopping",
    4: "stopped",
    5: "aborted",
}
BLUETOOTH_ERRORS = {
    0: "success",
    1: "radio not available",
    2: "Bluetooth advertising resource in use",
    4: "other Bluetooth error",
    5: "disabled by policy",
    6: "not supported by this Bluetooth adapter",
    7: "disabled by user",
    8: "consent required",
    9: "transport not supported",
}


def normalise_device_token(value: str) -> str:
    token = value.strip().upper()
    if not DEVICE_TOKEN_PATTERN.fullmatch(token):
        raise ValueError("device ID must be 1-16 characters: A-Z, 0-9, or '-'")
    return token


def build_payload(device_token: str) -> bytes:
    return COMP6733_PAYLOAD_PREFIX + normalise_device_token(device_token).encode("ascii")


async def bluetooth_preflight_error() -> str | None:
    """Return a user-facing adapter problem, or ``None`` when ready."""
    from winrt.windows.devices.bluetooth import BluetoothAdapter

    adapter = await BluetoothAdapter.get_default_async()
    if adapter is None:
        return "No Windows Bluetooth adapter was found"
    if not adapter.is_peripheral_role_supported:
        return "This Bluetooth adapter cannot advertise (peripheral role unsupported)"

    radio = await adapter.get_radio_async()
    if int(radio.state) != 1:  # Windows.Devices.Radios.RadioState.ON
        return "Bluetooth is turned off in Windows Settings"
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Advertise this Windows PC as a COMP6733 BLE device")
    parser.add_argument("--device-id", default=os.environ.get("BLE_DEVICE_ID"), help="Unique ID, e.g. PC-01")
    parser.add_argument("--backend-url", default=os.environ.get("BACKEND_URL"), help="Optional /api/bluetooth/readings URL")
    parser.add_argument(
        "--co-located-anchor",
        choices=("anchor-left", "anchor-right"),
        default=os.environ.get("COLOCATED_SCANNER_ID") or None,
        help="Set only when this PC is also one of the two anchors",
    )
    parser.add_argument("--self-rssi", type=int, default=-20)
    return parser.parse_args()


def _post_self_reading(args: argparse.Namespace, device_token: str) -> None:
    payload = {
        "message_type": "bluetooth_rssi",
        "scanner_id": args.co_located_anchor,
        "device_id": f"BT-PC-{device_token}",
        "device_name": f"Bluetooth PC {device_token}",
        "rssi": args.self_rssi,
        "tx_power": None,
    }
    try:
        response = requests.post(args.backend_url, json=payload, timeout=3.0)
        if not response.ok:
            print(f"Self reading rejected: {response.status_code} {response.text}", file=sys.stderr)
    except requests.RequestException as exc:
        print(f"Self reading failed: {exc}", file=sys.stderr)


def main() -> int:
    args = _parse_args()
    if not args.device_id:
        print("--device-id or BLE_DEVICE_ID is required", file=sys.stderr)
        return 2
    if args.co_located_anchor and not args.backend_url:
        print("--backend-url is required with --co-located-anchor", file=sys.stderr)
        return 2
    if not -120 <= args.self_rssi <= 0:
        print("--self-rssi must be between -120 and 0", file=sys.stderr)
        return 2

    try:
        device_token = normalise_device_token(args.device_id)
        payload = build_payload(device_token)
        from winrt.windows.devices.bluetooth.advertisement import (
            BluetoothLEAdvertisementPublisher,
            BluetoothLEManufacturerData,
        )
        from winrt.windows.storage.streams import DataWriter
    except (ImportError, ValueError) as exc:
        print(f"Cannot initialise Bluetooth advertiser: {exc}", file=sys.stderr)
        print("Install backend/requirements.txt in the Windows virtual environment.", file=sys.stderr)
        return 2

    preflight_error = asyncio.run(bluetooth_preflight_error())
    if preflight_error:
        print(f"Cannot start Bluetooth advertiser: {preflight_error}", file=sys.stderr)
        return 1

    writer = DataWriter()
    writer.write_bytes(payload)
    manufacturer_data = BluetoothLEManufacturerData()
    manufacturer_data.company_id = COMP6733_COMPANY_ID
    manufacturer_data.data = writer.detach_buffer()

    publisher = BluetoothLEAdvertisementPublisher()
    publisher.advertisement.manufacturer_data.append(manufacturer_data)
    status_event = threading.Event()
    result = {"status": 0, "error": 0}

    def status_changed(_sender, event_args) -> None:
        result["status"] = int(event_args.status)
        result["error"] = int(event_args.error)
        print(
            f"Bluetooth publisher: {PUBLISHER_STATUS.get(result['status'], result['status'])}"
            f" ({BLUETOOTH_ERRORS.get(result['error'], result['error'])})"
        )
        if result["status"] in (2, 5):
            status_event.set()

    token = publisher.add_status_changed(status_changed)
    publisher.start()
    status_event.wait(timeout=8.0)

    if result["status"] != 2:
        publisher.remove_status_changed(token)
        publisher.stop()
        print("Bluetooth advertising did not start. Turn Bluetooth on and close competing beacon apps.", file=sys.stderr)
        return 1

    print(f"Advertising actual PC as BT-PC-{device_token}. Press Ctrl+C to stop.")
    if args.co_located_anchor:
        print(f"Self-proximity heartbeat enabled for {args.co_located_anchor}.")

    try:
        while result["status"] == 2:
            if args.co_located_anchor:
                _post_self_reading(args, device_token)
            time.sleep(0.5)
        print("Bluetooth publisher stopped unexpectedly; presence heartbeat stopped.", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Stopping Bluetooth advertiser...")
    finally:
        publisher.stop()
        publisher.remove_status_changed(token)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
