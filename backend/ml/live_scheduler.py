from __future__ import annotations

import atexit
import os
import threading
from datetime import datetime, timezone
from typing import Any

from flask import Flask

from .live_service import run_live_prediction


class LivePredictionScheduler:
    def __init__(self, app: Flask) -> None:
        self.app = app
        self.interval_seconds = int(
            app.config["ML_LIVE_PREDICTION_INTERVAL_SECONDS"]
        )
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._last_started_at: str | None = None
        self._last_completed_at: str | None = None
        self._last_prediction_id: int | None = None
        self._last_error: str | None = None

    def start(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
            name="ml-live-prediction",
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": True,
                "running": bool(self._thread and self._thread.is_alive()),
                "interval_seconds": self.interval_seconds,
                "last_started_at": self._last_started_at,
                "last_completed_at": self._last_completed_at,
                "last_prediction_id": self._last_prediction_id,
                "last_error": self._last_error,
                "next_run_at": self._next_boundary().isoformat(),
            }

    def _run(self) -> None:
        while not self._stop.is_set():
            delay = max(
                0.1,
                (self._next_boundary() - datetime.now(timezone.utc)).total_seconds(),
            )
            if self._stop.wait(delay):
                return
            started = datetime.now(timezone.utc).isoformat()
            with self._lock:
                self._last_started_at = started
                self._last_error = None
            try:
                with self.app.app_context():
                    result = run_live_prediction(source="scheduler")
                with self._lock:
                    self._last_prediction_id = int(result["id"])
                    self._last_completed_at = datetime.now(timezone.utc).isoformat()
            except Exception as exc:
                self.app.logger.exception("Scheduled ML prediction failed")
                with self._lock:
                    self._last_error = f"{type(exc).__name__}: {exc}"
                    self._last_completed_at = datetime.now(timezone.utc).isoformat()

    def _next_boundary(self) -> datetime:
        now = datetime.now(timezone.utc)
        epoch = int(now.timestamp())
        next_epoch = epoch - (epoch % self.interval_seconds) + self.interval_seconds
        return datetime.fromtimestamp(next_epoch, tz=timezone.utc)


def start_live_prediction_scheduler(app: Flask) -> None:
    enabled = bool(app.config.get("ML_LIVE_PREDICTION_ENABLED", True))
    if not enabled or app.config.get("TESTING", False):
        app.extensions["ml_live_scheduler"] = None
        return
    if app.config.get("DEBUG") and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        app.extensions["ml_live_scheduler"] = None
        return
    scheduler = LivePredictionScheduler(app)
    app.extensions["ml_live_scheduler"] = scheduler
    scheduler.start()
    atexit.register(scheduler.stop)


def scheduler_status(app: Flask) -> dict[str, Any]:
    scheduler = app.extensions.get("ml_live_scheduler")
    if scheduler is None:
        return {
            "enabled": bool(app.config.get("ML_LIVE_PREDICTION_ENABLED", True)),
            "running": False,
            "interval_seconds": int(
                app.config["ML_LIVE_PREDICTION_INTERVAL_SECONDS"]
            ),
            "last_started_at": None,
            "last_completed_at": None,
            "last_prediction_id": None,
            "last_error": None,
            "next_run_at": None,
        }
    return scheduler.status()
