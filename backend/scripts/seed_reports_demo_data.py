"""
Seed realistic-looking demo data for the Reports tab.

Populates a week of history across every table the /api/reports/* endpoints
read from, so the Reports page shows real numbers instead of near-empty
ones:

  - occupancy_events         -> summary stats (avg/peak occupancy, hours tracked)
  - radar_readings           -> data completeness + fusion evaluation
  - environment_readings     -> data completeness
  - occupancy_ground_truth   -> fusion evaluation table (MAE / RMSE / gain)

Safe to re-run: it only INSERTs new rows (occupancy_ground_truth has a
UNIQUE(room_id, observed_at) constraint so re-running won't duplicate those
particular rows; event/reading tables will grow each run, which is fine for
demo purposes — delete instance/occupancy.db and restart the backend if you
want a clean slate).

Usage (from the backend/ directory, with the venv active):

    python scripts/seed_reports_demo_data.py
    python scripts/seed_reports_demo_data.py --days 14 --db instance/occupancy.db
"""

import argparse
import os
import random
import sqlite3
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEVICE_ID = "pico-01"
ROOM_ID = os.environ.get("REPORT_ROOM_ID", "K17-101")
_TZ_NAME = os.environ.get("REPORT_TIMEZONE", "Australia/Sydney")
try:
    LOCAL_TZ = ZoneInfo(_TZ_NAME)
except ZoneInfoNotFoundError:
    LOCAL_TZ = timezone.utc


def local_hour(dt: datetime) -> int:
    """Hour-of-day in the report's display timezone, so 'busy hours' land during actual daytime."""
    return dt.astimezone(LOCAL_TZ).hour

# A working room: quiet overnight, busy mid-morning / early afternoon, tapering
# off in the evening. Index = hour of day (0-23), value = relative "busyness".
HOURLY_WEIGHTS = [
    0, 0, 0, 0, 0, 0,           # 00:00-05:59  empty
    1, 3, 6, 9, 8, 7,           # 06:00-11:59  filling up
    6, 8, 9, 8, 6, 5,           # 12:00-17:59  afternoon activity
    3, 2, 1, 0, 0, 0,           # 18:00-23:59  winding down
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db",
        default=os.environ.get("DATABASE_PATH", "instance/occupancy.db"),
        help="Path to the SQLite database (default: instance/occupancy.db)",
    )
    parser.add_argument(
        "--days", type=int, default=7, help="How many days of history to generate (default: 7)"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed, for reproducible demo data"
    )
    return parser.parse_args()


def ensure_schema(conn: sqlite3.Connection) -> None:
    """Import the app's schema initializer so this works even against a brand-new db file."""
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from app.database import _SCHEMA  # noqa: PLC0415

    conn.executescript(_SCHEMA)
    conn.commit()


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def seed(conn: sqlite3.Connection, days: int, rng: random.Random) -> None:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=days)

    occupancy_rows = []
    radar_rows = []
    env_rows = []
    ground_truth_rows = []

    current_occupancy = 0
    event_id = 1
    cursor = start

    # --- occupancy_events + radar_readings + environment_readings ---------
    # Walk forward in ~4 minute steps for the whole window, occasionally
    # firing an entry/exit event based on the hour-of-day weight, and always
    # logging a radar + environment reading (these drive "data completeness").
    step = timedelta(minutes=4)
    while cursor < now:
        weight = HOURLY_WEIGHTS[local_hour(cursor)]
        # Mean-revert current_occupancy toward a per-hour target so the room
        # fills up and empties out realistically instead of drifting forever.
        target = round(weight * 1.2)
        fire_event = False
        if current_occupancy < target and rng.random() < 0.5:
            event, change, fire_event = "entry", 1, True
        elif current_occupancy > target and rng.random() < 0.5:
            event, change, fire_event = "exit", -1, True
        elif target > 0 and rng.random() < 0.05:
            # Occasional noise even at target, so it's not perfectly static.
            event, change = ("entry", 1) if rng.random() < 0.5 else ("exit", -1)
            fire_event = True

        if fire_event:
            current_occupancy = max(0, current_occupancy + change)
            occupancy_rows.append(
                (
                    DEVICE_ID,
                    event_id,
                    event,
                    change,
                    rng.randint(400, 2500),
                    int((cursor - start).total_seconds() * 1000),
                    iso(cursor),
                    "occupancy_event",
                    current_occupancy,
                    None,
                )
            )
            event_id += 1

        # Radar roughly tracks current occupancy with a little noise.
        radar_count = max(0, current_occupancy + rng.choice([-1, 0, 0, 0, 1]))
        radar_rows.append(
            (
                DEVICE_ID,
                int((cursor - start).total_seconds() * 1000),
                radar_count,
                "[]",
                iso(cursor),
            )
        )

        # CO2 climbs a bit with occupancy, temp/humidity wander gently.
        co2 = 420 + current_occupancy * 55 + rng.randint(-15, 15)
        temp = 21.5 + current_occupancy * 0.15 + rng.uniform(-0.3, 0.3)
        humidity = 45 + current_occupancy * 0.8 + rng.uniform(-2, 2)
        env_rows.append(
            (
                DEVICE_ID,
                int((cursor - start).total_seconds() * 1000),
                co2,
                round(temp, 1),
                round(humidity, 1),
                iso(cursor),
            )
        )

        cursor += step

    # --- occupancy_ground_truth --------------------------------------------
    # Simulate someone manually headcounting the room every ~2 hours during
    # open hours, with a value close to (but not identical to) the sensor
    # occupancy at that moment, so MAE/RMSE come out non-zero but reasonable.
    gt_cursor = start
    while gt_cursor < now:
        if HOURLY_WEIGHTS[local_hour(gt_cursor)] > 0:
            sensor_estimate = max(
                0,
                round(HOURLY_WEIGHTS[local_hour(gt_cursor)] * rng.uniform(0.4, 0.9)),
            )
            noise = rng.choice([-1, -1, 0, 0, 0, 1, 1])
            ground_truth_rows.append(
                (
                    ROOM_ID,
                    max(0, sensor_estimate + noise),
                    iso(gt_cursor),
                    "manual_headcount_demo",
                )
            )
        gt_cursor += timedelta(hours=2)

    conn.executemany(
        """
        INSERT OR IGNORE INTO occupancy_events
            (device_id, event_id, event, count_change, duration_ms, uptime_ms,
             received_at, message_type, radar_target_count, radar_targets_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        occupancy_rows,
    )
    conn.executemany(
        """
        INSERT INTO radar_readings
            (device_id, uptime_ms, target_count, targets_json, received_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        radar_rows,
    )
    conn.executemany(
        """
        INSERT INTO environment_readings
            (device_id, uptime_ms, co2_ppm, temperature_c, humidity_percent, received_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        env_rows,
    )
    conn.executemany(
        """
        INSERT OR IGNORE INTO occupancy_ground_truth
            (room_id, occupancy_count, observed_at, source)
        VALUES (?, ?, ?, ?)
        """,
        ground_truth_rows,
    )
    conn.commit()

    print(f"Inserted {len(occupancy_rows)} occupancy_events")
    print(f"Inserted {len(radar_rows)} radar_readings")
    print(f"Inserted {len(env_rows)} environment_readings")
    print(f"Inserted up to {len(ground_truth_rows)} occupancy_ground_truth rows (dupes skipped)")
    print(f"Room: {ROOM_ID}  |  Device: {DEVICE_ID}  |  Window: {iso(start)} -> {iso(now)}")


def main() -> None:
    args = parse_args()
    rng = random.Random(args.seed)

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        ensure_schema(conn)
        seed(conn, args.days, rng)
    finally:
        conn.close()

    print(f"\nDone. Seeded {args.days} day(s) of demo data into {args.db}")
    print("Restart/refresh the frontend and open the Reports tab (try 7D or 30D range).")


if __name__ == "__main__":
    main()