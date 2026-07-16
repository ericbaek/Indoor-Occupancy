"""
Tests for hardware_gateway.py — HTTP forwarding logic.

HTTP requests are mocked so these tests do not require a running backend.
Stdin input is simulated via io.StringIO.
"""

import io
import json
import sys
from unittest.mock import MagicMock, call, patch

import pytest

# Import the gateway module's internal helpers directly.
# The script lives at scripts/hardware_gateway.py, so add scripts/ to sys.path
# if needed.
import importlib
import os

# Ensure the scripts directory is importable.
_SCRIPTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "scripts"
)
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, os.path.abspath(_SCRIPTS_DIR))

import hardware_gateway as gw  # noqa: E402


BASE_URL = "http://localhost:5000"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _lines_to_stdin(lines: list[str]) -> io.StringIO:
    return io.StringIO("\n".join(lines) + "\n")


def _make_ok_response(status=201):
    resp = MagicMock()
    resp.ok = True
    resp.status_code = status
    resp.text = '{"success": true}'
    return resp


def _make_error_response(status=400):
    resp = MagicMock()
    resp.ok = False
    resp.status_code = status
    resp.text = '{"error": "bad request"}'
    return resp


# ---------------------------------------------------------------------------
# _forward — routing by message_type
# ---------------------------------------------------------------------------

def test_forward_radar_posts_to_radar_endpoint():
    message = {
        "message_type": "radar",
        "device_id": "pico-01",
        "uptime_ms": 1000,
        "target_count": 0,
        "targets": [],
    }
    with patch("hardware_gateway.requests.post", return_value=_make_ok_response()) as mock_post:
        gw._forward(BASE_URL, message)
        mock_post.assert_called_once()
        url_used = mock_post.call_args[0][0]
        assert url_used.endswith("/api/radar/readings")


def test_forward_occupancy_event_posts_to_occupancy_endpoint():
    message = {
        "message_type": "occupancy_event",
        "device_id": "pico-01",
        "event_id": 1,
        "event": "entry",
        "count_change": 1,
        "duration_ms": 800,
        "uptime_ms": 16400,
    }
    with patch("hardware_gateway.requests.post", return_value=_make_ok_response()) as mock_post:
        gw._forward(BASE_URL, message)
        mock_post.assert_called_once()
        url_used = mock_post.call_args[0][0]
        assert url_used.endswith("/api/occupancy/events")


def test_forward_unknown_message_type_does_not_post():
    message = {"message_type": "unknown_type", "device_id": "pico-01"}
    with patch("hardware_gateway.requests.post") as mock_post:
        gw._forward(BASE_URL, message)
        mock_post.assert_not_called()


# ---------------------------------------------------------------------------
# _process_line — JSON parsing
# ---------------------------------------------------------------------------

def test_process_line_valid_json_calls_forward():
    message = {"message_type": "radar", "device_id": "pico-01",
                "uptime_ms": 1, "target_count": 0, "targets": []}
    line = json.dumps(message)
    with patch("hardware_gateway._forward") as mock_fwd:
        gw._process_line(line, BASE_URL)
        mock_fwd.assert_called_once_with(BASE_URL, message)


def test_process_line_invalid_json_skips_silently():
    with patch("hardware_gateway._forward") as mock_fwd:
        gw._process_line("not valid json {{", BASE_URL)
        mock_fwd.assert_not_called()


def test_process_line_empty_line_skips_silently():
    with patch("hardware_gateway._forward") as mock_fwd:
        gw._process_line("   ", BASE_URL)
        mock_fwd.assert_not_called()


def test_process_line_non_object_json_skips():
    with patch("hardware_gateway._forward") as mock_fwd:
        gw._process_line("[1, 2, 3]", BASE_URL)
        mock_fwd.assert_not_called()


# ---------------------------------------------------------------------------
# _run_stdin — multiple lines processed correctly
# ---------------------------------------------------------------------------

def test_run_stdin_processes_multiple_lines():
    radar_msg = {"message_type": "radar", "device_id": "p",
                 "uptime_ms": 1, "target_count": 0, "targets": []}
    occ_msg = {"message_type": "occupancy_event", "device_id": "p",
               "event_id": 1, "event": "entry", "count_change": 1,
               "duration_ms": 100, "uptime_ms": 500}

    lines = [json.dumps(radar_msg), json.dumps(occ_msg)]
    fake_stdin = _lines_to_stdin(lines)

    calls_made = []

    def fake_forward(url, msg):
        calls_made.append(msg["message_type"])

    with patch("hardware_gateway._forward", side_effect=fake_forward), \
         patch("sys.stdin", fake_stdin):
        gw._run_stdin(BASE_URL)

    assert "radar" in calls_made
    assert "occupancy_event" in calls_made


def test_run_stdin_skips_bad_json_and_continues():
    good_msg = {"message_type": "radar", "device_id": "p",
                "uptime_ms": 1, "target_count": 0, "targets": []}
    lines = ["bad json {{{{", json.dumps(good_msg)]
    fake_stdin = _lines_to_stdin(lines)

    calls_made = []

    def fake_forward(url, msg):
        calls_made.append(msg["message_type"])

    with patch("hardware_gateway._forward", side_effect=fake_forward), \
         patch("sys.stdin", fake_stdin):
        gw._run_stdin(BASE_URL)

    # Only the good message should have been forwarded.
    assert calls_made == ["radar"]


def test_run_stdin_skips_unknown_message_type_and_continues():
    unknown_msg = {"message_type": "heartbeat", "device_id": "p"}
    good_msg = {"message_type": "radar", "device_id": "p",
                "uptime_ms": 1, "target_count": 0, "targets": []}
    lines = [json.dumps(unknown_msg), json.dumps(good_msg)]
    fake_stdin = _lines_to_stdin(lines)

    with patch("hardware_gateway.requests.post", return_value=_make_ok_response()) as mock_post, \
         patch("sys.stdin", fake_stdin):
        gw._run_stdin(BASE_URL)

    # Only the radar message should have triggered an HTTP call.
    assert mock_post.call_count == 1
    assert mock_post.call_args[0][0].endswith("/api/radar/readings")


# ---------------------------------------------------------------------------
# Connection failure — gateway continues after error
# ---------------------------------------------------------------------------

def test_gateway_continues_after_connection_error():
    import requests as req_mod

    msg1 = {"message_type": "radar", "device_id": "p",
             "uptime_ms": 1, "target_count": 0, "targets": []}
    msg2 = {"message_type": "radar", "device_id": "p",
             "uptime_ms": 2, "target_count": 0, "targets": []}
    lines = [json.dumps(msg1), json.dumps(msg2)]
    fake_stdin = _lines_to_stdin(lines)

    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise req_mod.exceptions.ConnectionError("refused")
        return _make_ok_response()

    with patch("hardware_gateway.requests.post", side_effect=fake_post), \
         patch("sys.stdin", fake_stdin):
        # Must not raise; the gateway should process both lines.
        gw._run_stdin(BASE_URL)

    assert call_count == 2
