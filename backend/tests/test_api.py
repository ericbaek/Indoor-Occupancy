from datetime import datetime, timedelta, timezone

import pytest

from app import create_app
from app.database import get_db


@pytest.fixture()
def report_app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": tmp_path / "api.db"})


@pytest.fixture()
def report_client(report_app):
    return report_app.test_client()


def insert_event(db, event_id, change, received_at):
    db.execute(
        """
        INSERT INTO occupancy_events
            (device_id, event_id, event, count_change, duration_ms, uptime_ms, received_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "pir-test",
            event_id,
            "entry" if change == 1 else "exit",
            change,
            100,
            event_id * 1000,
            received_at.isoformat(),
        ),
    )


def insert_radar(db, count, received_at):
    db.execute(
        """
        INSERT INTO radar_readings
            (device_id, uptime_ms, target_count, targets_json, received_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        ("radar-test", 1000, count, "[]", received_at.isoformat()),
    )


def insert_co2(db, received_at, ppm=650):
    db.execute(
        """
        INSERT INTO environment_readings
            (device_id, uptime_ms, co2_ppm, temperature_c, humidity_percent, received_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        ("co2-test", 1000, ppm, 22.5, 48.0, received_at.isoformat()),
    )


@pytest.mark.parametrize(
    ("token", "label"),
    [
        ("24h", "Last 24 hours"),
        ("7d", "Last 7 days"),
        ("30d", "Last 30 days"),
        ("90d", "Last 90 days"),
    ],
)
def test_summary_ranges(report_client, token, label):
    response = report_client.get(f"/api/reports/summary?range={token}")
    assert response.status_code == 200
    assert response.get_json()["range_label"] == label


def test_empty_summary(report_client):
    response = report_client.get("/api/reports/summary")
    assert response.status_code == 200
    assert response.get_json() == {
        "range_label": "Last 7 days",
        "total_hours_tracked": 0.0,
        "avg_occupancy": 0.0,
        "peak_occupancy": 0,
        "peak_at": None,
        "data_completeness_percent": 0,
    }


def test_invalid_range(report_client):
    response = report_client.get("/api/reports/summary?range=weekly")
    assert response.status_code == 400
    assert "24h, 7d, 30d, 90d" in response.get_json()["error"]


def test_summary_values(report_app, report_client):
    now = datetime.now(timezone.utc)
    with report_app.app_context():
        db = get_db()
        insert_event(db, 1, 1, now - timedelta(hours=2))
        insert_event(db, 2, 1, now - timedelta(hours=1))
        insert_radar(db, 2, now - timedelta(minutes=15))
        insert_co2(db, now - timedelta(minutes=10))
        db.commit()

    response = report_client.get("/api/reports/summary?range=24h")
    data = response.get_json()
    assert response.status_code == 200
    assert data["avg_occupancy"] == 0.1
    assert data["peak_occupancy"] == 2
    assert datetime.fromisoformat(data["peak_at"]).utcoffset() is not None
    assert data["total_hours_tracked"] == 0.3
    assert data["data_completeness_percent"] == 1


def test_evaluation_without_ground_truth(report_client):
    response = report_client.get("/api/reports/evaluation?range=7d")
    assert response.status_code == 200
    assert response.get_json() == {"metrics": []}


def test_evaluation_metrics(report_app, report_client):
    observed_at = datetime.now(timezone.utc) - timedelta(minutes=2)
    stored_at = observed_at.astimezone(timezone(timedelta(hours=10)))
    with report_app.app_context():
        db = get_db()
        insert_event(db, 1, 1, observed_at - timedelta(minutes=5))
        insert_radar(db, 2, observed_at - timedelta(seconds=1))
        db.execute(
            """
            INSERT INTO occupancy_ground_truth
                (room_id, occupancy_count, observed_at, source)
            VALUES (?, ?, ?, ?)
            """,
            ("K17-101", 2, stored_at.isoformat(), "manual"),
        )
        db.commit()

    response = report_client.get("/api/reports/evaluation?range=7d")
    assert response.status_code == 200
    assert response.get_json()["metrics"] == [
        {
            "model": "PIR only (baseline)",
            "mae": 1.0,
            "rmse": 1.0,
            "fusion_gain_percent": None,
            "sample_count": 1,
        },
        {
            "model": "PIR + mmWave fusion",
            "mae": 0.0,
            "rmse": 0.0,
            "fusion_gain_percent": 100.0,
            "sample_count": 1,
        },
    ]


def test_exports_and_downloads(report_app, report_client):
    with report_app.app_context():
        db = get_db()
        insert_co2(db, datetime.now(timezone.utc) - timedelta(minutes=1), 725)
        db.commit()

    response = report_client.get("/api/reports/exports?range=7d")
    exports = response.get_json()["exports"]
    assert response.status_code == 200
    assert [item["id"] for item in exports] == ["r1", "r2", "r3"]
    assert [item["format"] for item in exports] == ["csv", "pdf", "csv"]
    assert all(item["room"] == "K17-101" for item in exports)
    assert all(item["size_kb"] >= 1 for item in exports)

    summary = report_client.get("/api/reports/exports/r1/download?range=7d")
    evaluation = report_client.get("/api/reports/exports/r2/download?range=7d")
    co2 = report_client.get("/api/reports/exports/r3/download?range=7d")
    assert summary.status_code == 200
    assert summary.mimetype == "text/csv"
    assert b"total_hours_tracked" in summary.data
    assert evaluation.status_code == 200
    assert evaluation.mimetype == "application/pdf"
    assert evaluation.data.startswith(b"%PDF-1.4")
    assert evaluation.data.rstrip().endswith(b"%%EOF")
    assert co2.status_code == 200
    assert co2.mimetype == "text/csv"
    assert b"co2-test,725" in co2.data


def test_missing_export(report_client):
    response = report_client.get("/api/reports/exports/missing/download")
    assert response.status_code == 404
    assert response.get_json() == {"error": "Report export not found"}
