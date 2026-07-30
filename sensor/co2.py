"""
co2.py — MicroPython SCD41 CO₂ sensor driver
=============================================
Target board : Arduino Nano 33 BLE Sense Rev2 (running MicroPython)
Sensor       : DFRobot Gravity SCD41, SEN0536
Interface    : I²C, address 0x62
Wiring       : SDA → A4 (Pin 18), SCL → A5 (Pin 19), VCC → 3.3 V, GND → GND

Output
------
One JSON object per measurement printed to stdout (USB serial), approximately
every five seconds:

  {"message_type":"environment","device_id":"scd41-nano-01",
   "uptime_ms":12000,"co2_ppm":491,"temperature_c":23.6,"humidity_percent":37.9}

The gateway (backend/scripts/hardware_gateway.py --mode serial) reads these
lines and forwards them to POST /api/co2/readings.

Usage in Thonny
---------------
1. Select MicroPython (Arduino Nano 33 BLE Sense) interpreter and the correct
   COM port.
2. Run this file to verify JSON output every five seconds.
3. Save it to the Nano as main.py so it starts automatically on power-up.
4. IMPORTANT: Close Thonny before launching the gateway — only one program can
   hold the serial port at a time.
"""

import time
import ujson
from machine import I2C, Pin

# ---------------------------------------------------------------------------
# Hardware constants
# ---------------------------------------------------------------------------

# On the Arduino Nano 33 BLE Sense Rev2 under MicroPython the I²C pads are:
#   A4 (SDA) → machine pin 18
#   A5 (SCL) → machine pin 19
_SDA_PIN = 18
_SCL_PIN = 19
_I2C_FREQ = 100_000          # 100 kHz — safe for 3.3 V SCD41

# SCD41 7-bit I²C address
_SCD41_ADDR = 0x62

# SCD41 commands (16-bit, MSB first)
_CMD_STOP_PERIODIC   = 0x3F86
_CMD_START_PERIODIC  = 0x21B1
_CMD_DATA_READY      = 0xE4B8
_CMD_READ_MEASUREMENT = 0xEC05

# Device identifier used in every JSON message — must match the backend
# device_id expected by GET /api/co2/latest/scd41-nano-01
DEVICE_ID = "scd41-nano-01"

# Measurement interval in seconds (SCD41 runs at 1 reading per 5 s)
MEASURE_INTERVAL_S = 5


# ---------------------------------------------------------------------------
# CRC-8 (Sensirion standard: poly 0x31, init 0xFF, no reflection)
# ---------------------------------------------------------------------------

def _crc8(data: bytes) -> int:
    """Return the CRC-8 checksum over *data* using Sensirion's parameters."""
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


# ---------------------------------------------------------------------------
# Low-level I²C helpers
# ---------------------------------------------------------------------------

def _write_cmd(i2c: I2C, cmd: int) -> None:
    """Send a 2-byte command word to the SCD41."""
    i2c.writeto(_SCD41_ADDR, bytes([cmd >> 8, cmd & 0xFF]))


def _read_response(i2c: I2C, cmd: int, n_words: int) -> list:
    """
    Send *cmd*, pause 1 ms, then read *n_words* data words (each word is
    2 data bytes + 1 CRC byte = 3 bytes per word).

    Returns a list of validated uint16 values, or raises ValueError on CRC
    mismatch, or OSError on I²C failure (caller handles both).
    """
    _write_cmd(i2c, cmd)
    time.sleep_ms(1)

    raw = i2c.readfrom(_SCD41_ADDR, n_words * 3)

    values = []
    for i in range(n_words):
        msb  = raw[i * 3]
        lsb  = raw[i * 3 + 1]
        crc  = raw[i * 3 + 2]
        expected = _crc8(bytes([msb, lsb]))
        if crc != expected:
            raise ValueError(
                "CRC mismatch on word {}: got 0x{:02X}, expected 0x{:02X}".format(
                    i, crc, expected
                )
            )
        values.append((msb << 8) | lsb)

    return values


# ---------------------------------------------------------------------------
# SCD41 operations
# ---------------------------------------------------------------------------

def scd41_stop_periodic(i2c: I2C) -> None:
    """Stop any in-progress periodic measurement (required before re-init)."""
    _write_cmd(i2c, _CMD_STOP_PERIODIC)
    time.sleep_ms(500)          # SCD41 datasheet: ≥ 500 ms after stop


def scd41_start_periodic(i2c: I2C) -> None:
    """Start continuous periodic measurement at 1 reading per 5 s."""
    _write_cmd(i2c, _CMD_START_PERIODIC)


def scd41_data_ready(i2c: I2C) -> bool:
    """
    Return True when a new measurement is available.

    The SCD41 sets bits [10:0] of the data-ready word to a non-zero value
    when data is ready.  Bit 11 is always 0 after the first reading.
    """
    words = _read_response(i2c, _CMD_DATA_READY, 1)
    return (words[0] & 0x07FF) != 0


def scd41_read_measurement(i2c: I2C) -> tuple:
    """
    Read the latest CO₂, temperature and humidity from the SCD41.

    Returns (co2_ppm: int, temperature_c: float, humidity_percent: float).
    Raises ValueError on CRC error, OSError on I²C bus error.
    """
    words = _read_response(i2c, _CMD_READ_MEASUREMENT, 3)

    co2_raw  = words[0]
    temp_raw = words[1]
    hum_raw  = words[2]

    co2_ppm        = co2_raw
    temperature_c  = round(-45.0 + 175.0 * temp_raw / 65535.0, 2)
    humidity_pct   = round(100.0 * hum_raw / 65535.0, 2)

    return co2_ppm, temperature_c, humidity_pct


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main() -> None:
    print("SCD41 CO2 sensor starting on", DEVICE_ID)

    # Initialise I²C bus
    i2c = I2C(1, sda=Pin(_SDA_PIN), scl=Pin(_SCL_PIN), freq=_I2C_FREQ)

    # Stop any stale periodic measurement, then start a fresh one
    try:
        scd41_stop_periodic(i2c)
    except OSError as exc:
        print("Warning: stop_periodic failed (sensor may be idle):", exc)

    try:
        scd41_start_periodic(i2c)
    except OSError as exc:
        print("Error: could not start periodic measurement:", exc)
        # Without this command the sensor will not produce data; pause then
        # retry in the loop so a transient power glitch is survivable.

    print("Waiting for first measurement (~5 s) ...")
    time.sleep(MEASURE_INTERVAL_S)

    while True:
        try:
            # Poll data-ready before reading to avoid reading stale data
            if not scd41_data_ready(i2c):
                time.sleep_ms(500)
                continue

            co2_ppm, temperature_c, humidity_percent = scd41_read_measurement(i2c)

            message = {
                "message_type":    "environment",
                "device_id":       DEVICE_ID,
                "uptime_ms":       time.ticks_ms(),
                "co2_ppm":         co2_ppm,
                "temperature_c":   temperature_c,
                "humidity_percent": humidity_percent,
            }
            print(ujson.dumps(message))

        except ValueError as exc:
            # CRC mismatch — log and skip this reading; sensor keeps running
            print("CRC error (skipping reading):", exc)

        except OSError as exc:
            # I²C bus error — log and attempt to recover
            print("I2C error (will retry):", exc)
            time.sleep_ms(1000)
            # Re-issue start in case the sensor reset
            try:
                scd41_stop_periodic(i2c)
                scd41_start_periodic(i2c)
            except OSError:
                pass  # Will retry on next loop iteration

        time.sleep(MEASURE_INTERVAL_S)


main()
