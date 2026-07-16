from machine import Pin
from time import sleep, ticks_ms, ticks_diff
from rd03d import RD03D
import ujson

# hardware Setup

pir_outside = Pin(15, Pin.IN)
pir_inside = Pin(14, Pin.IN)

radar = RD03D(uart_id=1, tx_pin=4, rx_pin=5, multi_mode=True)

# configuration

TIMEOUT_MS = 3000
RADAR_SEND_INTERVAL_MS = 500
DEVICE_ID = "doorway-pico-01"

# states

last_outside = pir_outside.value()
last_inside = pir_inside.value()
first_sensor = None
first_time = 0
event_number = 0
last_radar_send = ticks_ms()
latest_targets = []

# printing Json data to terminal
def send_json(data):
    print(ujson.dumps(data))
    print()

# return target's information
def target_to_dict(target, target_number):
    if target is None:
        return None

    if (target.x == 0 and target.y == 0 and target.speed == 0):
        return None

    return {
        "target_id": target_number,
        "x_mm": round(target.x, 1),
        "y_mm": round(target.y, 1),
        "distance_mm": round(target.distance, 1),
        "angle_deg": round(target.angle, 1),
        "speed_cm_s": target.speed
    }

# return info of all available targets
def read_radar_targets():
    targets = []

    for target_number in range(1, 4):
        target = radar.get_target(target_number)
        target_data = target_to_dict(target, target_number)

        if target_data is not None:
            targets.append(target_data)

    return targets

# sending radar json data
def send_radar_data(targets):
    message = {
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": ticks_ms(),
        "target_count": len(targets),
        "targets": targets
    }

    send_json(message)

# sending PIR sensor data + radar data
def send_occupancy_event(event_type, count_change, duration_ms):
    global event_number
    event_number += 1
    message = {
        "message_type": "occupancy_event",
        "device_id": DEVICE_ID,
        "event_id": event_number,
        "event": event_type,
        "count_change": count_change,
        "duration_ms": duration_ms,
        "uptime_ms": ticks_ms(),
        "radar": {
            "target_count": len(latest_targets),
            "targets": latest_targets
        }
    }

    send_json(message)

# main Loop

while True:
    if radar.update():
        latest_targets = read_radar_targets()
        now = ticks_ms()
        
        # send radar data after every 500 ms
        if ticks_diff(now, last_radar_send) >= RADAR_SEND_INTERVAL_MS:
            send_radar_data(latest_targets)
            last_radar_send = now

    # read PIR sensors
    outside = pir_outside.value()
    inside = pir_inside.value()
    outside_triggered = outside == 1 and last_outside == 0
    inside_triggered = inside == 1 and last_inside == 0

    if first_sensor is None:
        if outside_triggered and not inside_triggered:
            first_sensor = "outside"
            first_time = ticks_ms()

        elif inside_triggered and not outside_triggered:
            first_sensor = "inside"
            first_time = ticks_ms()

    elif first_sensor == "outside":
        if inside_triggered:
            duration = ticks_diff(ticks_ms(), first_time)

            send_occupancy_event(
                event_type="entry",
                count_change=1,
                duration_ms=duration
            )
            first_sensor = None

        elif ticks_diff(ticks_ms(), first_time) > TIMEOUT_MS:
            first_sensor = None

    elif first_sensor == "inside":
        if outside_triggered:
            duration = ticks_diff(ticks_ms(), first_time)

            send_occupancy_event(
                event_type="exit",
                count_change=-1,
                duration_ms=duration
            )
            first_sensor = None

        elif ticks_diff(ticks_ms(), first_time) > TIMEOUT_MS:
            first_sensor = None

    last_outside = outside
    last_inside = inside
    sleep(0.02)