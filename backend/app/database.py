import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

from flask import Flask, g


def get_db(app: Flask | None = None) -> sqlite3.Connection:
    if "db" not in g:
        if app is not None:
            db_path = app.config["DATABASE"]
        else:
            from flask import current_app
            db_path = current_app.config["DATABASE"]

        g.db = sqlite3.connect(db_path, detect_types=sqlite3.PARSE_DECLTYPES)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


def close_connection(exception: BaseException | None = None) -> None:
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Schema — all CREATE TABLE statements are idempotent (IF NOT EXISTS).
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sensor_events (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    room_id       TEXT    NOT NULL,
    device_id     TEXT,
    sensor_type   TEXT    NOT NULL,
    event_type    TEXT    NOT NULL,
    value         REAL,
    event_count   INTEGER,
    payload       TEXT    NOT NULL,
    received_at   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS room_state (
    room_id          TEXT    PRIMARY KEY,
    occupancy_count  INTEGER NOT NULL DEFAULT 0,
    occupancy_level  TEXT    NOT NULL DEFAULT 'Empty',
    last_event       TEXT,
    updated_at       TEXT
);

CREATE TABLE IF NOT EXISTS occupancy_events (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id           TEXT    NOT NULL,
    event_id            INTEGER NOT NULL,
    event               TEXT    NOT NULL CHECK(event IN ('entry', 'exit')),
    count_change        INTEGER NOT NULL CHECK(count_change IN (1, -1)),
    duration_ms         INTEGER NOT NULL CHECK(duration_ms >= 0),
    uptime_ms           INTEGER NOT NULL CHECK(uptime_ms >= 0),
    received_at         TEXT    NOT NULL,
    message_type        TEXT,
    radar_target_count  INTEGER,
    radar_targets_json  TEXT,
    UNIQUE (device_id, event_id)
);

CREATE TABLE IF NOT EXISTS radar_latest (
    device_id   TEXT    PRIMARY KEY,
    uptime_ms   INTEGER NOT NULL,
    target_count INTEGER NOT NULL,
    targets_json TEXT    NOT NULL,
    received_at TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS radar_readings (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT    NOT NULL,
    uptime_ms    INTEGER NOT NULL,
    target_count INTEGER NOT NULL,
    targets_json TEXT    NOT NULL,
    received_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS environment_latest (
    device_id        TEXT    PRIMARY KEY,
    uptime_ms        INTEGER NOT NULL,
    co2_ppm          INTEGER NOT NULL,
    temperature_c    REAL    NOT NULL,
    humidity_percent REAL    NOT NULL,
    received_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS environment_readings (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id        TEXT    NOT NULL,
    uptime_ms        INTEGER NOT NULL,
    co2_ppm          INTEGER NOT NULL,
    temperature_c    REAL    NOT NULL,
    humidity_percent REAL    NOT NULL,
    received_at      TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS bluetooth_readings (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    scanner_id  TEXT    NOT NULL,
    tag_id      TEXT    NOT NULL,
    rssi        INTEGER NOT NULL,
    tx_power    INTEGER,
    received_at TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bluetooth_tag_time
    ON bluetooth_readings(tag_id, received_at);

CREATE INDEX IF NOT EXISTS idx_bluetooth_scanner_time
    ON bluetooth_readings(scanner_id, received_at);
"""


def _migrate_occupancy_events(db: sqlite3.Connection) -> None:
    """Safely add new columns to occupancy_events if they do not already exist.

    SQLite does not support ALTER TABLE … ADD COLUMN IF NOT EXISTS, so we check
    PRAGMA table_info first.  This is safe to call multiple times.
    """
    existing = {
        row["name"]
        for row in db.execute("PRAGMA table_info(occupancy_events)").fetchall()
    }

    new_columns = [
        ("message_type",       "TEXT"),
        ("radar_target_count", "INTEGER"),
        ("radar_targets_json", "TEXT"),
    ]

    for col_name, col_type in new_columns:
        if col_name not in existing:
            db.execute(
                f"ALTER TABLE occupancy_events ADD COLUMN {col_name} {col_type}"
            )

    db.commit()


def init_db(app: Flask) -> None:
    db = get_db(app)
    db.executescript(_SCHEMA)
    db.commit()
    _migrate_occupancy_events(db)


# ---------------------------------------------------------------------------
# sensor_events / room_state helpers (unchanged)
# ---------------------------------------------------------------------------

def insert_event(
    *,
    room_id: str,
    device_id: str | None,
    sensor_type: str,
    event_type: str,
    value: float | None,
    event_count: int | None,
    occupancy_count: int,
    occupancy_level: str,
    payload: dict[str, Any],
) -> tuple[int, str]:
    received_at = _utc_now()
    payload_json = json.dumps(payload)

    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO sensor_events
                (room_id, device_id, sensor_type, event_type,
                 value, event_count, payload, received_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (room_id, device_id, sensor_type, event_type,
             value, event_count, payload_json, received_at),
        )
        event_id = cursor.lastrowid

        db.execute(
            """
            INSERT INTO room_state
                (room_id, occupancy_count, occupancy_level, last_event, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(room_id) DO UPDATE SET
                occupancy_count = excluded.occupancy_count,
                occupancy_level = excluded.occupancy_level,
                last_event      = excluded.last_event,
                updated_at      = excluded.updated_at
            """,
            (room_id, occupancy_count, occupancy_level, event_type, received_at),
        )

        db.commit()
    except Exception:
        db.rollback()
        raise

    return event_id, received_at


def get_room_state(room_id: str) -> sqlite3.Row | None:
    db = get_db()
    return db.execute(
        "SELECT * FROM room_state WHERE room_id = ?", (room_id,)
    ).fetchone()


def reset_room(room_id: str) -> str:
    updated_at = _utc_now()
    db = get_db()
    try:
        db.execute(
            """
            INSERT INTO room_state
                (room_id, occupancy_count, occupancy_level, last_event, updated_at)
            VALUES (?, 0, 'Empty', 'RESET', ?)
            ON CONFLICT(room_id) DO UPDATE SET
                occupancy_count = 0,
                occupancy_level = 'Empty',
                last_event      = 'RESET',
                updated_at      = excluded.updated_at
            """,
            (room_id, updated_at),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return updated_at


def get_events(
    *,
    room_id: str | None = None,
    sensor_type: str | None = None,
    event_type: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    limit = min(limit, 200)

    query = "SELECT * FROM sensor_events WHERE 1=1"
    params: list[Any] = []

    if room_id is not None:
        query += " AND room_id = ?"
        params.append(room_id)
    if sensor_type is not None:
        query += " AND sensor_type = ?"
        params.append(sensor_type)
    if event_type is not None:
        query += " AND event_type = ?"
        params.append(event_type)

    query += " ORDER BY id DESC LIMIT ?"
    params.append(limit)

    rows = get_db().execute(query, params).fetchall()
    events = []
    for row in rows:
        event = dict(row)
        try:
            event["payload"] = json.loads(event["payload"])
        except (json.JSONDecodeError, TypeError):
            pass
        events.append(event)

    return events


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# PIR doorway occupancy events
# ---------------------------------------------------------------------------

def insert_occupancy_event(
    *,
    device_id: str,
    event_id: int,
    event: str,
    count_change: int,
    duration_ms: int,
    uptime_ms: int,
    message_type: str | None = None,
    radar_target_count: int | None = None,
    radar_targets_json: str | None = None,
) -> tuple[int, str]:
    """Insert a single PIR occupancy event and return (row_id, received_at).

    Raises sqlite3.IntegrityError when the (device_id, event_id) pair already
    exists in the database (duplicate hardware event).
    """
    received_at = _utc_now()
    db = get_db()
    cursor = db.execute(
        """
        INSERT INTO occupancy_events
            (device_id, event_id, event, count_change,
             duration_ms, uptime_ms, received_at,
             message_type, radar_target_count, radar_targets_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (device_id, event_id, event, count_change,
         duration_ms, uptime_ms, received_at,
         message_type, radar_target_count, radar_targets_json),
    )
    db.commit()
    return cursor.lastrowid, received_at


def get_occupancy_events(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent PIR occupancy events, newest first."""
    limit = min(max(1, limit), 200)
    rows = get_db().execute(
        "SELECT * FROM occupancy_events ORDER BY id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def get_occupancy_total() -> tuple[int, str | None]:
    """Return (current_occupancy, updated_at) derived from occupancy_events.

    current_occupancy is clamped to zero — it will never be negative.
    updated_at is the received_at of the most recent event, or None if there
    are no events yet.
    """
    row = get_db().execute(
        "SELECT SUM(count_change) AS total, MAX(received_at) AS updated_at "
        "FROM occupancy_events"
    ).fetchone()
    total: int = row["total"] if row["total"] is not None else 0
    return max(0, total), row["updated_at"]


# ---------------------------------------------------------------------------
# Radar storage helpers
# ---------------------------------------------------------------------------

def upsert_radar_latest(
    *,
    device_id: str,
    uptime_ms: int,
    target_count: int,
    targets: list[dict[str, Any]],
) -> str:
    """Update (or insert) the latest radar reading for a device.

    Uses INSERT OR REPLACE so the row is always the most recent snapshot.
    Returns the received_at timestamp.
    """
    received_at = _utc_now()
    targets_json = json.dumps(targets)
    db = get_db()
    db.execute(
        """
        INSERT INTO radar_latest (device_id, uptime_ms, target_count, targets_json, received_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            uptime_ms    = excluded.uptime_ms,
            target_count = excluded.target_count,
            targets_json = excluded.targets_json,
            received_at  = excluded.received_at
        """,
        (device_id, uptime_ms, target_count, targets_json, received_at),
    )
    db.commit()
    return received_at


def insert_radar_reading_if_throttled(
    *,
    device_id: str,
    uptime_ms: int,
    target_count: int,
    targets: list[dict[str, Any]],
) -> bool:
    """Insert a radar history record if at least 1 second has elapsed since
    the last stored record for this device.  Returns True if a row was inserted.

    This throttles the radar_readings table so it never stores more than one
    row per device per second.
    """
    db = get_db()
    row = db.execute(
        "SELECT MAX(received_at) AS last_at FROM radar_readings WHERE device_id = ?",
        (device_id,),
    ).fetchone()

    last_at: str | None = row["last_at"] if row else None

    now = datetime.now(timezone.utc)

    if last_at is not None:
        try:
            last_dt = datetime.fromisoformat(last_at)
            elapsed = (now - last_dt).total_seconds()
            if elapsed < 1.0:
                return False
        except ValueError:
            pass  # Unparseable timestamp — allow the insert.

    received_at = now.isoformat()
    targets_json = json.dumps(targets)
    db.execute(
        """
        INSERT INTO radar_readings (device_id, uptime_ms, target_count, targets_json, received_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (device_id, uptime_ms, target_count, targets_json, received_at),
    )
    db.commit()
    return True


def get_radar_latest_all() -> list[dict[str, Any]]:
    """Return the latest radar snapshot for every known device."""
    rows = get_db().execute(
        "SELECT * FROM radar_latest ORDER BY device_id"
    ).fetchall()
    result = []
    for row in rows:
        d = dict(row)
        try:
            d["targets"] = json.loads(d.pop("targets_json"))
        except (json.JSONDecodeError, TypeError):
            d["targets"] = []
        result.append(d)
    return result


def get_radar_latest_for_device(device_id: str) -> dict[str, Any] | None:
    """Return the latest radar snapshot for a specific device, or None."""
    row = get_db().execute(
        "SELECT * FROM radar_latest WHERE device_id = ?", (device_id,)
    ).fetchone()
    if row is None:
        return None
    d = dict(row)
    try:
        d["targets"] = json.loads(d.pop("targets_json"))
    except (json.JSONDecodeError, TypeError):
        d["targets"] = []
    return d


# ---------------------------------------------------------------------------
# Environment / CO2 sensor storage helpers
# ---------------------------------------------------------------------------

def upsert_environment_latest(
    *,
    device_id: str,
    uptime_ms: int,
    co2_ppm: int,
    temperature_c: float,
    humidity_percent: float,
) -> str:
    """Update (or insert) the latest environment reading for a device.

    Uses INSERT … ON CONFLICT so the row is always the most recent snapshot.
    Returns the received_at timestamp.
    """
    received_at = _utc_now()
    db = get_db()
    db.execute(
        """
        INSERT INTO environment_latest
            (device_id, uptime_ms, co2_ppm, temperature_c, humidity_percent, received_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(device_id) DO UPDATE SET
            uptime_ms        = excluded.uptime_ms,
            co2_ppm          = excluded.co2_ppm,
            temperature_c    = excluded.temperature_c,
            humidity_percent = excluded.humidity_percent,
            received_at      = excluded.received_at
        """,
        (device_id, uptime_ms, co2_ppm, temperature_c, humidity_percent, received_at),
    )
    db.commit()
    return received_at


def insert_environment_reading_if_throttled(
    *,
    device_id: str,
    uptime_ms: int,
    co2_ppm: int,
    temperature_c: float,
    humidity_percent: float,
) -> bool:
    """Insert an environment history record if at least 5 seconds have elapsed
    since the last stored record for this device.  Returns True if a row was
    inserted.

    The 5-second throttle matches the SCD41 sensor's measurement interval.
    """
    db = get_db()
    row = db.execute(
        "SELECT MAX(received_at) AS last_at FROM environment_readings WHERE device_id = ?",
        (device_id,),
    ).fetchone()

    last_at: str | None = row["last_at"] if row else None

    now = datetime.now(timezone.utc)

    if last_at is not None:
        try:
            last_dt = datetime.fromisoformat(last_at)
            elapsed = (now - last_dt).total_seconds()
            if elapsed < 5.0:
                return False
        except ValueError:
            pass  # Unparseable timestamp — allow the insert.

    received_at = now.isoformat()
    db.execute(
        """
        INSERT INTO environment_readings
            (device_id, uptime_ms, co2_ppm, temperature_c, humidity_percent, received_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (device_id, uptime_ms, co2_ppm, temperature_c, humidity_percent, received_at),
    )
    db.commit()
    return True


def get_environment_latest_all() -> list[dict[str, Any]]:
    """Return the latest environment reading for every known device."""
    rows = get_db().execute(
        "SELECT * FROM environment_latest ORDER BY device_id"
    ).fetchall()
    return [dict(row) for row in rows]


def get_environment_latest_for_device(device_id: str) -> dict[str, Any] | None:
    """Return the latest environment reading for a specific device, or None."""
    row = get_db().execute(
        "SELECT * FROM environment_latest WHERE device_id = ?", (device_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_environment_history(
    device_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return recent environment readings for a device, newest first."""
    limit = min(max(1, limit), 200)
    rows = get_db().execute(
        "SELECT * FROM environment_readings WHERE device_id = ? ORDER BY id DESC LIMIT ?",
        (device_id, limit),
    ).fetchall()
    return [dict(row) for row in rows]


# ---------------------------------------------------------------------------
# BLE / Bluetooth RSSI storage helpers
# ---------------------------------------------------------------------------

def insert_bluetooth_reading(
    *,
    scanner_id: str,
    tag_id: str,
    rssi: int,
    tx_power: int | None,
) -> str:
    """Insert a single BLE RSSI reading and return the server-generated
    received_at timestamp.

    Timestamps are always generated server-side; do not accept timestamps
    from anchor laptops to avoid clock-skew issues.
    """
    received_at = _utc_now()
    db = get_db()
    db.execute(
        """
        INSERT INTO bluetooth_readings (scanner_id, tag_id, rssi, tx_power, received_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (scanner_id, tag_id, rssi, tx_power, received_at),
    )
    db.commit()
    return received_at


def get_recent_bluetooth_readings(
    tag_id: str,
    window_seconds: float = 2.0,
) -> list[dict[str, Any]]:
    """Return BLE readings for *tag_id* received within the last *window_seconds*.

    Returns a list of dicts with keys: scanner_id, rssi, tx_power, received_at.
    """
    now = datetime.now(timezone.utc)
    cutoff = (now - __import__('datetime').timedelta(seconds=window_seconds)).isoformat()
    rows = get_db().execute(
        """
        SELECT scanner_id, rssi, tx_power, received_at
        FROM bluetooth_readings
        WHERE tag_id = ? AND received_at >= ?
        ORDER BY received_at ASC
        """,
        (tag_id, cutoff),
    ).fetchall()
    return [dict(row) for row in rows]


def get_active_tags(
    inactive_timeout_seconds: float = 5.0,
) -> list[dict[str, Any]]:
    """Return one row per tag_id that has had a reading within the timeout.

    Each row: tag_id, last_seen_at (MAX received_at).
    """
    now = datetime.now(timezone.utc)
    cutoff = (now - __import__('datetime').timedelta(seconds=inactive_timeout_seconds)).isoformat()
    rows = get_db().execute(
        """
        SELECT tag_id, MAX(received_at) AS last_seen_at
        FROM bluetooth_readings
        WHERE received_at >= ?
        GROUP BY tag_id
        ORDER BY tag_id
        """,
        (cutoff,),
    ).fetchall()
    return [dict(row) for row in rows]


def cleanup_old_bluetooth_readings(retention_hours: float = 24.0) -> int:
    """Delete BLE readings older than *retention_hours* and return the count
    of deleted rows.

    Call this from a periodic maintenance task, not on every request.
    """
    now = datetime.now(timezone.utc)
    cutoff = (now - __import__('datetime').timedelta(hours=retention_hours)).isoformat()
    db = get_db()
    cursor = db.execute(
        "DELETE FROM bluetooth_readings WHERE received_at < ?",
        (cutoff,),
    )
    db.commit()
    return cursor.rowcount

