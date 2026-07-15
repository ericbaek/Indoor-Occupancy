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
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id    TEXT    NOT NULL,
    event_id     INTEGER NOT NULL,
    event        TEXT    NOT NULL CHECK(event IN ('entry', 'exit')),
    count_change INTEGER NOT NULL CHECK(count_change IN (1, -1)),
    duration_ms  INTEGER NOT NULL CHECK(duration_ms >= 0),
    uptime_ms    INTEGER NOT NULL CHECK(uptime_ms >= 0),
    received_at  TEXT    NOT NULL,
    UNIQUE (device_id, event_id)
);
"""


def init_db(app: Flask) -> None:
    db = get_db(app)
    db.executescript(_SCHEMA)
    db.commit()


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
             duration_ms, uptime_ms, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (device_id, event_id, event, count_change,
         duration_ms, uptime_ms, received_at),
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
