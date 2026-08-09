from machine import Pin
from time import sleep, ticks_diff, ticks_ms
from rd03d import RD03D
import ujson

#sending JSON
def send_json(data):
    print(ujson.dumps(data))
    print()

#hardware pin setup
pir_outside = Pin(15, Pin.IN)
pir_inside = Pin(14, Pin.IN)
radar = RD03D(uart_id=1, tx_pin=4, rx_pin=5, multi_mode=True)

#config
DEVICE_ID = "doorway-pico-01"
RADAR_SEND_INTERVAL_MS = 500

#the area x < -350 is inside
#the area x > 350 is outside
#area [-350, 350] is considered 
INSIDE_X_MAX = -350
OUTSIDE_X_MIN = 350

#tracking and noise rejection
SIDE_CONFIRM_FRAMES = 4
TRACK_TIMEOUT_MS = 700
MAX_MATCH_DISTANCE_MM = 600
EVENT_COOLDOWN_MS = 700
PIR_FUSION_WINDOW_MS = 3000

#keeping track of event id
EVENT_COUNTER_FILE = "occupancy_event_id.txt"
EVENT_ID_START = 1000000

#states
last_outside = pir_outside.value()
last_inside = pir_inside.value()
last_outside_pir_ms = None
last_inside_pir_ms = None
last_radar_send = ticks_ms()
latest_targets = []
tracks = []
next_track_id = 1

#take event number from the event counter file
def load_event_number():
    try:
        with open(EVENT_COUNTER_FILE, "r") as counter_file:
            return int(counter_file.read().strip())
    except (OSError, ValueError):
        return EVENT_ID_START


event_number = load_event_number()

#writing new event number
def next_event_id():
    global event_number
    event_number += 1

    try:
        with open(EVENT_COUNTER_FILE, "w") as counter_file:
            counter_file.write(str(event_number))
    except OSError:
        pass

    return event_number

#sending radar tracking data in JSON format
def send_radar_data(targets, now):
    send_json({
        "message_type": "radar",
        "device_id": DEVICE_ID,
        "uptime_ms": now,
        "target_count": len(targets),
        "targets": targets,
    })

#sending occupancy event (entry/exit) with the occupancy change
#along with radar data
def send_occupancy_event(event_type, track, now):
    if event_type == "entry":
        count_change = 1
    else:
        count_change = -1

    send_json({
        "message_type": "occupancy_event",
        "device_id": DEVICE_ID,
        "event_id": next_event_id(),
        "event": event_type,
        "count_change": count_change,
        "duration_ms": track["last_crossing_duration_ms"],
        "uptime_ms": now,
        "radar": {
            "target_count": len(latest_targets),
            "targets": latest_targets,
        },
        "detection_source": "mmwave",
        "track_id": track["track_id"],
        "pir_fusion": get_pir_fusion(now),
    })

#get supporting PIR state
def update_pir_state(now):
    global last_outside
    global last_inside
    global last_outside_pir_ms
    global last_inside_pir_ms

    outside = pir_outside.value()
    inside = pir_inside.value()

    if outside == 1 and last_outside == 0:
        last_outside_pir_ms = now

    if inside == 1 and last_inside == 0:
        last_inside_pir_ms = now

    last_outside = outside
    last_inside = inside


def pir_seen_recently(trigger_time, now):
    if trigger_time is None:
        return False
    age = ticks_diff(now, trigger_time)
    return 0 <= age <= PIR_FUSION_WINDOW_MS

#get PIR confidence rating
def get_pir_fusion(now):
    outside_seen = pir_seen_recently(last_outside_pir_ms, now)
    inside_seen = pir_seen_recently(last_inside_pir_ms, now)

    if outside_seen and inside_seen:
        confidence = "high"
    elif outside_seen or inside_seen:
        confidence = "medium"
    else:
        confidence = "radar_only"

    return {
        "outside_pir_seen": outside_seen,
        "inside_pir_seen": inside_seen,
        "confidence": confidence,
    }

#check if target is inside or outside
def stable_side(x_mm):
    if x_mm <= INSIDE_X_MAX:
        return "inside"
    if x_mm >= OUTSIDE_X_MIN:
        return "outside"
    return None

#if not inside or outside, then target must be in the doorway
def display_zone(x_mm):
    side = stable_side(x_mm)
    return side if side is not None else "neutral"

#get target data to input into dictionary
def target_to_dict(target, radar_slot):
    if target is None:
        return None
    if target.x == 0 and target.y == 0 and target.speed == 0:
        return None

    return {
        "target_id": radar_slot,
        "track_id": None,
        "zone": display_zone(target.x),
        "x_mm": round(target.x, 1),
        "y_mm": round(target.y, 1),
        "distance_mm": round(target.distance, 1),
        "angle_deg": round(target.angle, 1),
        "speed_cm_s": target.speed,
    }

#reading every target slot to get target positions
def read_radar_targets():
    targets = []
    for radar_slot in range(1, 4):
        target_data = target_to_dict(radar.get_target(radar_slot), radar_slot)
        if target_data is not None:
            targets.append(target_data)
    return targets

#get target distance from radar
def distance_squared(track, detection):
    dx = track["x_mm"] - detection["x_mm"]
    dy = track["y_mm"] - detection["y_mm"]
    return dx * dx + dy * dy

#create a new tracked person data from a radar detection
def make_track(track_id, detection, now):
    return {
        "track_id": track_id,
        "x_mm": detection["x_mm"],
        "y_mm": detection["y_mm"],
        "first_seen_ms": now,
        "last_seen_ms": now,
        "frames_seen": 1,
        "candidate_side": None,
        "candidate_frames": 0,
        "stable_side": None,
        "stable_since_ms": now,
        "origin_side": None,
        "last_event_ms": None,
        "last_crossing_duration_ms": 0,
    }

#confirm which side a track is on and return 'entry' or 'exit' when track crosses
def update_track_side(track, detection, now):
    side = stable_side(detection["x_mm"])

    if side is None:
        track["candidate_side"] = None
        track["candidate_frames"] = 0
        return None

    if track["candidate_side"] == side:
        track["candidate_frames"] += 1
    else:
        track["candidate_side"] = side
        track["candidate_frames"] = 1

    if track["candidate_frames"] < SIDE_CONFIRM_FRAMES:
        return None
    if track["stable_side"] == side:
        return None

    previous_side = track["stable_side"]

    if previous_side is None:
        track["stable_side"] = side
        track["origin_side"] = side
        track["stable_since_ms"] = now
        return None

    if track["last_event_ms"] is not None:
        if ticks_diff(now, track["last_event_ms"]) < EVENT_COOLDOWN_MS:
            return None

    event_type = None
    if previous_side == "outside" and side == "inside":
        event_type = "entry"
    elif previous_side == "inside" and side == "outside":
        event_type = "exit"

    track["last_crossing_duration_ms"] = ticks_diff(
        now,
        track["stable_since_ms"],
    )
    track["stable_side"] = side
    track["stable_since_ms"] = now

    if event_type is not None:
        track["last_event_ms"] = now

    return event_type

#match current radar detections to existing tracks and return completed crossing events
def update_tracks(detections, now):
    global tracks
    global next_track_id

    tracks = [
        track for track in tracks
        if ticks_diff(now, track["last_seen_ms"]) <= TRACK_TIMEOUT_MS
    ]

    unmatched_tracks = list(range(len(tracks)))
    unmatched_detections = list(range(len(detections)))
    matches = []
    maximum_distance_squared = MAX_MATCH_DISTANCE_MM * MAX_MATCH_DISTANCE_MM

    while unmatched_tracks and unmatched_detections:
        best_track = None
        best_detection = None
        best_distance = None

        for track_index in unmatched_tracks:
            for detection_index in unmatched_detections:
                gap = distance_squared(
                    tracks[track_index],
                    detections[detection_index],
                )
                if best_distance is None or gap < best_distance:
                    best_track = track_index
                    best_detection = detection_index
                    best_distance = gap

        if best_distance is None or best_distance > maximum_distance_squared:
            break

        matches.append((best_track, best_detection))
        unmatched_tracks.remove(best_track)
        unmatched_detections.remove(best_detection)

    completed_events = []

    for track_index, detection_index in matches:
        track = tracks[track_index]
        detection = detections[detection_index]

        track["x_mm"] = detection["x_mm"]
        track["y_mm"] = detection["y_mm"]
        track["last_seen_ms"] = now
        track["frames_seen"] += 1
        detection["track_id"] = track["track_id"]

        event_type = update_track_side(track, detection, now)
        if event_type is not None:
            completed_events.append((event_type, track))

    for detection_index in unmatched_detections:
        detection = detections[detection_index]
        track = make_track(next_track_id, detection, now)
        tracks.append(track)
        detection["track_id"] = next_track_id
        update_track_side(track, detection, now)
        next_track_id += 1

    return completed_events

#main loop
while True:
    now = ticks_ms()
    update_pir_state(now)

    if radar.update():
        now = ticks_ms()
        latest_targets = read_radar_targets()
        completed_events = update_tracks(latest_targets, now)

        for event_type, completed_track in completed_events:
            send_occupancy_event(event_type, completed_track, now)

        if ticks_diff(now, last_radar_send) >= RADAR_SEND_INTERVAL_MS:
            send_radar_data(latest_targets, now)
            last_radar_send = now

    sleep(0.02)
