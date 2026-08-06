from __future__ import annotations

import json
import math
import statistics
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from flask import current_app

try:
    from app.database import get_db
except ModuleNotFoundError:
    from backend.app.database import get_db

from .config import TIMEZONE


def aggregate_sensor_window(window_end: datetime | None = None) -> dict[str, Any]:
    end_utc = _resolve_window_end(window_end)
    window_seconds = int(current_app.config["ML_SENSOR_WINDOW_SECONDS"])
    start_utc = end_utc - timedelta(seconds=window_seconds)
    local_zone = ZoneInfo(TIMEZONE)
    start_local = start_utc.astimezone(local_zone)
    end_local = end_utc.astimezone(local_zone)

    time_features = _time_features(start_local)
    pir, pir_meta = _aggregate_pir(start_utc, end_utc)
    radar, radar_meta = _aggregate_radar(start_utc, end_utc, window_seconds)
    environment, environment_meta = _aggregate_environment(
        start_utc, end_utc, window_seconds
    )
    ble, ble_meta = _aggregate_ble(start_utc, end_utc, window_seconds)

    record: dict[str, Any] = {
        "window_start": start_local.isoformat(),
        "window_end": end_local.isoformat(),
        **time_features,
        **pir,
        **radar,
        **environment,
        "ventilation_current": current_app.config["ML_DEFAULT_VENTILATION"],
        **ble,
        "minimum_ventilation": current_app.config["ML_MINIMUM_VENTILATION"],
        "maximum_ventilation": current_app.config["ML_MAXIMUM_VENTILATION"],
        "aggregation_metadata": {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_seconds": window_seconds,
            "source_timezone": TIMEZONE,
            "pir": pir_meta,
            "radar": radar_meta,
            "co2": environment_meta,
            "ble": ble_meta,
        },
    }
    return record


def aligned_window_end(now: datetime | None = None) -> datetime:
    current = _as_utc(now or datetime.now(timezone.utc))
    interval = int(current_app.config["ML_LIVE_PREDICTION_INTERVAL_SECONDS"])
    epoch = int(current.timestamp())
    aligned = epoch - (epoch % interval)
    return datetime.fromtimestamp(aligned, tz=timezone.utc)


def parse_window_end(value: object) -> datetime:
    if not isinstance(value, str):
        raise ValueError("window_end must be an ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("window_end must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError("window_end must include a timezone offset")
    return parsed


def _resolve_window_end(window_end: datetime | None) -> datetime:
    if window_end is None:
        return aligned_window_end()
    return _as_utc(window_end)


def _time_features(start_local: datetime) -> dict[str, int | float]:
    open_hour = int(current_app.config["ML_ROOM_OPEN_HOUR"])
    operating_minutes = int(current_app.config["ML_ROOM_OPERATING_MINUTES"])
    open_time = start_local.replace(
        hour=open_hour, minute=0, second=0, microsecond=0
    )
    elapsed = int((start_local - open_time).total_seconds() // 60)
    minutes_since_open = min(max(elapsed, 0), operating_minutes)
    phase = 2.0 * math.pi * minutes_since_open / operating_minutes
    return {
        "day_of_week_num": start_local.weekday(),
        "is_weekend": int(start_local.weekday() >= 5),
        "hour": start_local.hour,
        "minute": start_local.minute,
        "minutes_since_open": minutes_since_open,
        "time_sin": round(math.sin(phase), 6),
        "time_cos": round(math.cos(phase), 6),
    }


def _aggregate_pir(
    start: datetime,
    end: datetime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        """
        SELECT event, count_change, duration_ms, received_at
        FROM occupancy_events
        WHERE received_at >= ? AND received_at < ?
        ORDER BY received_at ASC, id ASC
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    total_row = db.execute(
        """
        SELECT SUM(count_change) AS total, MAX(received_at) AS last_at
        FROM occupancy_events
        WHERE received_at < ?
        """,
        (end.isoformat(),),
    ).fetchone()

    entries = sum(1 for row in rows if row["event"] == "entry")
    exits = sum(1 for row in rows if row["event"] == "exit")
    durations = [float(row["duration_ms"]) for row in rows]
    cumulative = max(0, int(total_row["total"] or 0))
    has_history = total_row["last_at"] is not None
    values = {
        "pir_entry_count": entries,
        "pir_exit_count": exits,
        "pir_net_count_change": entries - exits,
        "pir_event_count": len(rows),
        "pir_entry_event_count": entries,
        "pir_exit_event_count": exits,
        "pir_total_detected_people": len(rows),
        "pir_max_people_per_event": 1 if rows else 0,
        "pir_mean_duration_ms": round(statistics.fmean(durations), 4)
        if durations
        else 0.0,
        "pir_cumulative_estimate": cumulative,
        "pir_stale_flag": int(not has_history),
    }
    metadata = {
        "raw_event_count": len(rows),
        "last_event_at": total_row["last_at"],
        "freshness_supported": False,
    }
    return values, metadata


def _aggregate_radar(
    start: datetime,
    end: datetime,
    window_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        """
        SELECT device_id, target_count, targets_json, received_at
        FROM radar_readings
        WHERE received_at >= ? AND received_at < ?
        ORDER BY received_at ASC, id ASC
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    latest = db.execute(
        "SELECT MAX(received_at) AS last_at FROM radar_readings WHERE received_at < ?",
        (end.isoformat(),),
    ).fetchone()["last_at"]
    known_devices = int(
        db.execute("SELECT COUNT(*) AS count FROM radar_latest").fetchone()["count"]
    )
    device_count = max(1, known_devices, len({row["device_id"] for row in rows}))
    expected_interval = float(current_app.config["ML_RADAR_EXPECTED_INTERVAL_SECONDS"])
    expected = max(1, round(window_seconds / expected_interval) * device_count)
    missing_ratio = _missing_ratio(len(rows), expected)
    stale = _is_stale(
        latest,
        end,
        float(current_app.config["ML_RADAR_STALE_SECONDS"]),
    )

    speeds: list[float] = []
    distances: list[float] = []
    for row in rows:
        for target in _targets(row["targets_json"]):
            speed = _number(target.get("speed_cm_s"))
            distance = _number(target.get("distance_mm"))
            if speed is not None:
                speeds.append(abs(speed))
            if distance is not None:
                distances.append(distance)

    counts = [int(row["target_count"]) for row in rows]
    values = {
        "radar_presence_ratio": round(
            sum(count > 0 for count in counts) / len(counts), 4
        )
        if counts
        else None,
        "radar_mean_target_count": round(statistics.fmean(counts), 4)
        if counts
        else None,
        "radar_max_target_count": max(counts) if counts else None,
        "radar_mean_abs_speed_cm_s": round(statistics.fmean(speeds), 4)
        if speeds
        else None,
        "radar_mean_distance_mm": round(statistics.fmean(distances), 4)
        if distances
        else None,
        "radar_missing_ratio": missing_ratio,
        "radar_stale_flag": int(stale),
    }
    metadata = {
        "raw_reading_count": len(rows),
        "expected_reading_count": expected,
        "known_device_count": device_count,
        "last_reading_at": latest,
        "stale": stale,
    }
    return values, metadata


def _aggregate_environment(
    start: datetime,
    end: datetime,
    window_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    db = get_db()
    rows = db.execute(
        """
        SELECT device_id, co2_ppm, temperature_c, humidity_percent, received_at
        FROM environment_readings
        WHERE received_at >= ? AND received_at < ?
        ORDER BY received_at ASC, id ASC
        """,
        (start.isoformat(), end.isoformat()),
    ).fetchall()
    latest = db.execute(
        """
        SELECT MAX(received_at) AS last_at
        FROM environment_readings
        WHERE received_at < ?
        """,
        (end.isoformat(),),
    ).fetchone()["last_at"]
    known_devices = int(
        db.execute("SELECT COUNT(*) AS count FROM environment_latest").fetchone()[
            "count"
        ]
    )
    device_count = max(1, known_devices, len({row["device_id"] for row in rows}))
    expected_interval = float(current_app.config["ML_CO2_EXPECTED_INTERVAL_SECONDS"])
    expected = max(1, round(window_seconds / expected_interval) * device_count)
    missing_ratio = _missing_ratio(len(rows), expected)
    stale = _is_stale(
        latest,
        end,
        float(current_app.config["ML_CO2_STALE_SECONDS"]),
    )

    co2 = [float(row["co2_ppm"]) for row in rows]
    temperatures = [float(row["temperature_c"]) for row in rows]
    humidities = [float(row["humidity_percent"]) for row in rows]
    delta = co2[-1] - co2[0] if len(co2) >= 2 else 0.0 if co2 else None
    elapsed_minutes = 0.0
    if len(rows) >= 2:
        first = _parse_db_time(rows[0]["received_at"])
        last = _parse_db_time(rows[-1]["received_at"])
        elapsed_minutes = max((last - first).total_seconds() / 60.0, 0.0)
    rate = delta / elapsed_minutes if delta is not None and elapsed_minutes > 0 else 0.0 if co2 else None
    quality_problem = not rows or stale or missing_ratio > 0.5
    values = {
        "co2_mean_ppm": round(statistics.fmean(co2), 4) if co2 else None,
        "co2_max_ppm": max(co2) if co2 else None,
        "co2_delta_ppm": round(delta, 4) if delta is not None else None,
        "co2_rate_ppm_per_min": round(rate, 4) if rate is not None else None,
        "temperature_mean_c": round(statistics.fmean(temperatures), 4)
        if temperatures
        else None,
        "humidity_mean_percent": round(statistics.fmean(humidities), 4)
        if humidities
        else None,
        "co2_missing_ratio": missing_ratio,
        "co2_quality_flag": int(quality_problem),
        "co2_stale_flag": int(stale),
    }
    metadata = {
        "raw_reading_count": len(rows),
        "expected_reading_count": expected,
        "known_device_count": device_count,
        "last_reading_at": latest,
        "stale": stale,
    }
    return values, metadata


def _aggregate_ble(
    start: datetime,
    end: datetime,
    window_seconds: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    left_id = current_app.config["ML_BLE_LEFT_SCANNER_ID"]
    right_id = current_app.config["ML_BLE_RIGHT_SCANNER_ID"]
    rows = get_db().execute(
        """
        SELECT scanner_id, tag_id, rssi, received_at
        FROM bluetooth_readings
        WHERE received_at >= ? AND received_at < ?
          AND scanner_id IN (?, ?)
        ORDER BY received_at ASC, id ASC
        """,
        (start.isoformat(), end.isoformat(), left_id, right_id),
    ).fetchall()
    left = [float(row["rssi"]) for row in rows if row["scanner_id"] == left_id]
    right = [float(row["rssi"]) for row in rows if row["scanner_id"] == right_id]
    all_rssi = left + right
    left_mean = statistics.fmean(left) if left else None
    right_mean = statistics.fmean(right) if right else None
    difference = (
        left_mean - right_mean
        if left_mean is not None and right_mean is not None
        else None
    )
    observed_seconds = {
        int(_parse_db_time(row["received_at"]).timestamp()) for row in rows
    }
    presence_ratio = min(1.0, len(observed_seconds) / max(1, window_seconds))
    missing_ratio = round(1.0 - presence_ratio, 4)
    side = _ble_side(left_mean, right_mean)
    quality_problem = not rows or left_mean is None or right_mean is None or missing_ratio > 0.5
    values = {
        "ble_left_rssi_mean_dbm": round(left_mean, 4)
        if left_mean is not None
        else None,
        "ble_right_rssi_mean_dbm": round(right_mean, 4)
        if right_mean is not None
        else None,
        "ble_left_right_rssi_diff_db": round(difference, 4)
        if difference is not None
        else None,
        "ble_rssi_variance": round(statistics.pvariance(all_rssi), 4)
        if len(all_rssi) >= 2
        else 0.0 if all_rssi else None,
        "ble_signal_presence_ratio": round(presence_ratio, 4),
        "ble_dominant_side_estimate": side,
        "ble_missing_ratio": missing_ratio,
        "ble_quality_flag": int(quality_problem),
    }
    metadata = {
        "raw_reading_count": len(rows),
        "left_reading_count": len(left),
        "right_reading_count": len(right),
        "active_tag_count": len({row["tag_id"] for row in rows}),
        "covered_seconds": len(observed_seconds),
        "left_scanner_id": left_id,
        "right_scanner_id": right_id,
    }
    return values, metadata


def _ble_side(left: float | None, right: float | None) -> str:
    if left is None and right is None:
        return "NO_SIGNAL"
    if right is None:
        return "LEFT"
    if left is None:
        return "RIGHT"
    threshold = float(current_app.config["ML_BLE_SWITCH_THRESHOLD_DB"])
    difference = left - right
    if difference >= threshold:
        return "LEFT"
    if difference <= -threshold:
        return "RIGHT"
    return "BALANCED"


def _targets(raw: str) -> list[dict[str, Any]]:
    try:
        value = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(value, list):
        return []
    return [target for target in value if isinstance(target, dict)]


def _number(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _missing_ratio(actual: int, expected: int) -> float:
    return round(max(0.0, min(1.0, 1.0 - actual / max(1, expected))), 4)


def _is_stale(raw: str | None, end: datetime, threshold_seconds: float) -> bool:
    if raw is None:
        return True
    return (end - _parse_db_time(raw)).total_seconds() > threshold_seconds


def _parse_db_time(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("window_end must include timezone information")
    return value.astimezone(timezone.utc)
