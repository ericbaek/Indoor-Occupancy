"""
co2.py — MicroPython SCD41 CO₂ sensor driver
Board  : Arduino Nano 33 BLE Sense Rev2
Sensor : DFRobot Gravity SCD41, SEN0536, I²C 0x62
Wiring : SDA → A4 (Pin 18), SCL → A5 (Pin 19), VCC → 3.3 V, GND → GND

Outputs one JSON line every 5 s:
  {"message_type":"environment","device_id":"scd41-nano-01",
   "uptime_ms":12000,"co2_ppm":491,"temperature_c":23.6,"humidity_percent":37.9}

Run in Thonny (MicroPython interpreter), then save to Nano as main.py.
Close Thonny before starting the gateway.
"""

import time
try:
    import ujson as json  # MicroPython
except ImportError:
    import json           # CircuitPython
from machine import I2C, Pin

_SDA_PIN = 18
_SCL_PIN = 19
_I2C_FREQ = 100_000

_SCD41_ADDR       = 0x62
_CMD_STOP_PERIODIC    = 0x3F86
_CMD_START_PERIODIC   = 0x21B1
_CMD_DATA_READY       = 0xE4B8
_CMD_READ_MEASUREMENT = 0xEC05

DEVICE_ID = "scd41-nano-01"
MEASURE_INTERVAL_S = 5


def _crc8(data: bytes) -> int:
    crc = 0xFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc << 1) ^ 0x31) & 0xFF if crc & 0x80 else (crc << 1) & 0xFF
    return crc


def _write_cmd(i2c: I2C, cmd: int) -> None:
    i2c.writeto(_SCD41_ADDR, bytes([cmd >> 8, cmd & 0xFF]))


def _read_response(i2c: I2C, cmd: int, n_words: int) -> list:
    _write_cmd(i2c, cmd)
    time.sleep_ms(1)
    raw = i2c.readfrom(_SCD41_ADDR, n_words * 3)
    values = []
    for i in range(n_words):
        msb, lsb, crc = raw[i*3], raw[i*3+1], raw[i*3+2]
        if crc != _crc8(bytes([msb, lsb])):
            raise ValueError("CRC mismatch on word {}".format(i))
        values.append((msb << 8) | lsb)
    return values


def scd41_stop_periodic(i2c: I2C) -> None:
    _write_cmd(i2c, _CMD_STOP_PERIODIC)
    time.sleep_ms(500)


def scd41_start_periodic(i2c: I2C) -> None:
    _write_cmd(i2c, _CMD_START_PERIODIC)


def scd41_data_ready(i2c: I2C) -> bool:
    words = _read_response(i2c, _CMD_DATA_READY, 1)
    return (words[0] & 0x07FF) != 0


def scd41_read_measurement(i2c: I2C) -> tuple:
    words = _read_response(i2c, _CMD_READ_MEASUREMENT, 3)
    co2_ppm       = words[0]
    temperature_c = round(-45.0 + 175.0 * words[1] / 65535.0, 2)
    humidity_pct  = round(100.0 * words[2] / 65535.0, 2)
    return co2_ppm, temperature_c, humidity_pct


def main() -> None:
    i2c = I2C(1, sda=Pin(_SDA_PIN), scl=Pin(_SCL_PIN), freq=_I2C_FREQ)

    try:
        scd41_stop_periodic(i2c)
    except OSError as exc:
        print("Warning: stop_periodic failed:", exc)

    try:
        scd41_start_periodic(i2c)
    except OSError as exc:
        print("Error: start_periodic failed:", exc)

    time.sleep(MEASURE_INTERVAL_S)

    while True:
        try:
            if not scd41_data_ready(i2c):
                time.sleep_ms(500)
                continue

            co2_ppm, temperature_c, humidity_percent = scd41_read_measurement(i2c)

            print(json.dumps({
                "message_type":    "environment",
                "device_id":       DEVICE_ID,
                "uptime_ms":       time.ticks_ms(),
                "co2_ppm":         co2_ppm,
                "temperature_c":   temperature_c,
                "humidity_percent": humidity_percent,
            }))

        except ValueError as exc:
            print("CRC error:", exc)

        except OSError as exc:
            print("I2C error:", exc)
            time.sleep_ms(1000)
            try:
                scd41_stop_periodic(i2c)
                scd41_start_periodic(i2c)
            except OSError:
                pass

        time.sleep(MEASURE_INTERVAL_S)


main()
