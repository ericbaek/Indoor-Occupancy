"""Windowed Bluetooth signal scanner for the Left/Right room heatmap.

Run the same program on both anchor computers and set ``ANCHOR_ID`` to either
``left-anchor`` or ``right-anchor``. During each short scan window the scanner:

1. groups repeated advertisements by Bluetooth address,
2. takes the median RSSI for each address,
3. keeps only the strongest few representative signals, and
4. sends their median RSSI and a 0-100 score to the Flask backend.

The address count is never used as the heatmap value or a person estimate.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import os
import statistics
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

ANCHOR_ID = os.environ.get("ANCHOR_ID") or os.environ.get("SCANNER_ID")
BACKEND_URL = os.environ.get("BACKEND_URL")
SCAN_WINDOW_SECONDS = float(os.environ.get("BLE_SCAN_WINDOW_SECONDS", "4"))
STRONGEST_SIGNAL_COUNT = int(os.environ.get("BLE_STRONGEST_SIGNAL_COUNT", "3"))
MINIMUM_RSSI = float(os.environ.get("BLE_MINIMUM_RSSI", "-100"))
MAXIMUM_RSSI = float(os.environ.get("BLE_MAXIMUM_RSSI", "-40"))
KNOWN_ANCHOR_IDS = {"left-anchor", "right-anchor"}


def rssi_to_score(
    rssi: float,
    *,
    minimum_rssi: float = MINIMUM_RSSI,
    maximum_rssi: float = MAXIMUM_RSSI,
) -> float:
    """Convert RSSI to a linearly scaled score between 0 and 100."""
    if maximum_rssi <= minimum_rssi:
        raise ValueError("maximum_rssi must be greater than minimum_rssi")
    clamped = max(minimum_rssi, min(maximum_rssi, float(rssi)))
    return round(
        (clamped - minimum_rssi) / (maximum_rssi - minimum_rssi) * 100.0,
        2,
    )


def collect_observation(
    device: BLEDevice,
    advertisement_data: AdvertisementData,
    observations: dict[str, list[float]],
) -> None:
    """Add one valid RSSI reading to its address group."""
    address = str(device.address or "").strip()
    rssi = advertisement_data.rssi
    if not address or isinstance(rssi, bool) or not isinstance(rssi, (int, float)):
        return
    if not -120 <= float(rssi) <= 0:
        return
    observations.setdefault(address, []).append(float(rssi))


def summarise_window(
    observations: dict[str, list[float]],
    *,
    strongest_count: int = STRONGEST_SIGNAL_COUNT,
) -> dict[str, float | int | None]:
    """Reduce a scan window without summing signals or using address count."""
    if strongest_count < 1:
        raise ValueError("strongest_count must be at least 1")

    representative_rssi = [
        float(statistics.median(readings))
        for readings in observations.values()
        if readings
    ]
    representative_rssi.sort(reverse=True)
    strongest = representative_rssi[:strongest_count]

    if not strongest:
        return {
            "average_rssi": None,
            "signal_score": 0.0,
            "observed_address_count": 0,
            "strongest_signal_count": 0,
        }

    overall_rssi = round(float(statistics.median(strongest)), 2)
    return {
        "average_rssi": overall_rssi,
        "signal_score": rssi_to_score(overall_rssi),
        # Debug-only metrics. They are logged locally and not sent as the
        # heatmap measurement or exposed as occupancy/device counts.
        "observed_address_count": len(representative_rssi),
        "strongest_signal_count": len(strongest),
    }


def build_payload(anchor_id: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor_id": anchor_id,
        "average_rssi": summary["average_rssi"],
        "signal_score": summary["signal_score"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def _post_summary(payload: dict[str, Any]) -> None:
    try:
        response = requests.post(BACKEND_URL, json=payload, timeout=5.0)
        if not response.ok:
            log.warning(
                "Backend rejected signal window: %s - %s",
                response.status_code,
                response.text,
            )
    except requests.exceptions.ConnectionError:
        log.error("Cannot connect to backend at %s", BACKEND_URL)
    except requests.exceptions.Timeout:
        log.warning("Timeout sending signal window to %s", BACKEND_URL)
    except requests.RequestException as exc:  # pragma: no cover
        log.error("HTTP request failed: %s", exc)


async def main() -> None:
    if ANCHOR_ID not in KNOWN_ANCHOR_IDS:
        log.error("ANCHOR_ID must be left-anchor or right-anchor")
        raise SystemExit(1)
    if not BACKEND_URL:
        log.error("BACKEND_URL must point to /api/bluetooth/signals")
        raise SystemExit(1)
    if SCAN_WINDOW_SECONDS <= 0:
        log.error("BLE_SCAN_WINDOW_SECONDS must be greater than 0")
        raise SystemExit(1)
    if STRONGEST_SIGNAL_COUNT < 1:
        log.error("BLE_STRONGEST_SIGNAL_COUNT must be at least 1")
        raise SystemExit(1)

    observations: dict[str, list[float]] = {}

    def on_detection(device: BLEDevice, data: AdvertisementData) -> None:
        collect_observation(device, data, observations)

    scanner = BleakScanner(detection_callback=on_detection)
    log.info("Starting %s with %.1f-second windows", ANCHOR_ID, SCAN_WINDOW_SECONDS)
    log.info("Sending signal intensity to %s", BACKEND_URL)

    try:
        await scanner.start()
        while True:
            await asyncio.sleep(SCAN_WINDOW_SECONDS)
            completed_window = observations
            observations = {}
            summary = summarise_window(completed_window)
            payload = build_payload(ANCHOR_ID, summary)
            await asyncio.to_thread(_post_summary, payload)
            log.info(
                "Window: RSSI=%s dBm score=%.1f/100 (top %d of %d addresses)",
                summary["average_rssi"] if summary["average_rssi"] is not None else "none",
                summary["signal_score"],
                summary["strongest_signal_count"],
                summary["observed_address_count"],
            )
    finally:
        await scanner.stop()
        log.info("Scanner stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
