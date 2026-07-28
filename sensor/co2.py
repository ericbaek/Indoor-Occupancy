from machine import Pin, I2C
from time import sleep, ticks_ms
import ujson

SCD41_ADDRESS = 0x62
DEVICE_ID = "scd41-nano-01"

# use this for nano
i2c = I2C(
    0,
    sda=Pin(31), # this is the A4 pin
    scl=Pin(2),  # this is the A5 pin
    freq=100000
)

# use this for pico
# i2c = I2C(
#     0,
#     sda=Pin(8),
#     scl=Pin(9),
#     freq=100000
# )

def crc8(data):
    crc = 0xFF

    for byte in data:
        crc ^= byte

        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x31) & 0xFF
            else:
                crc = (crc << 1) & 0xFF

    return crc

def send_command(command):
    data = bytes([
        (command >> 8) & 0xFF,
        command & 0xFF
    ])

    i2c.writeto(SCD41_ADDRESS, data)

def data_is_ready():
    send_command(0xE4B8)
    sleep(0.001)

    data = i2c.readfrom(SCD41_ADDRESS, 3)

    if crc8(data[0:2]) != data[2]:
        raise RuntimeError("Data-ready CRC error")

    status = (data[0] << 8) | data[1]

    return (status & 0x07FF) != 0


def read_measurement():
    send_command(0xEC05)
    sleep(0.001)

    data = i2c.readfrom(SCD41_ADDRESS, 9)

    co2_bytes = data[0:2]
    temperature_bytes = data[3:5]
    humidity_bytes = data[6:8]

    if crc8(co2_bytes) != data[2]:
        raise RuntimeError("CO2 CRC error")

    if crc8(temperature_bytes) != data[5]:
        raise RuntimeError("Temperature CRC error")

    if crc8(humidity_bytes) != data[8]:
        raise RuntimeError("Humidity CRC error")

    raw_co2 = (
        co2_bytes[0] << 8
    ) | co2_bytes[1]

    raw_temperature = (
        temperature_bytes[0] << 8
    ) | temperature_bytes[1]

    raw_humidity = (
        humidity_bytes[0] << 8
    ) | humidity_bytes[1]

    co2 = raw_co2
    temperature = -45 + (175 * raw_temperature / 65535)
    humidity = 100 * raw_humidity / 65535

    return co2, temperature, humidity


def print_json(co2, temperature, humidity):
    message = {
        "message_type": "environment",
        "device_id": DEVICE_ID,
        "uptime_ms": ticks_ms(),
        "co2_ppm": co2,
        "temperature_c": round(temperature, 1),
        "humidity_percent": round(humidity, 1)
    }

    print(ujson.dumps(message))

# start periodic measurement
send_command(0x21B1)
print("Starting periodic measurements...")

# first reading takes about 5 seconds
sleep(5)

while True:
    try:
        if data_is_ready():
            co2, temperature, humidity = read_measurement()

            print_json(
                co2,
                temperature,
                humidity
            )

    except OSError as error:
        print("SCD41 communication error:", error)

    except RuntimeError as error:
        print("SCD41 measurement error:", error)

    sleep(1)
