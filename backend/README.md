# Indoor Occupancy Backend

Flask + SQLite backend for privacy-preserving indoor occupancy monitoring.

---

## Project Purpose

This backend is part of a university IoT project (COMP6733) that monitors
room occupancy using PIR and mmWave radar sensors attached to a Raspberry Pi
Pico.  The Flask server acts as the data ingestion and query layer between a
gateway program (running on a host PC) and a frontend dashboard.

> **Important:** The Flask server does **not** communicate directly with the
> Raspberry Pi Pico.  The intended data flow is:
>
> ```
> Pico (sensor firmware)
>   → serial USB output
>   → gateway program (running on host PC, reads serial port)
>   → HTTP POST request
>   → Flask backend  (/api/events)
>   → SQLite database
>   → frontend dashboard (/api/rooms/<room_id>/status)
> ```

---

## Backend Responsibilities

- Receive sensor events via HTTP from the gateway program
- Store raw sensor events in a SQLite database
- Maintain the current occupancy count per room
- Provide room status to the frontend dashboard
- Provide recent sensor event history for debugging

---

## System Architecture

```
frontend/ (React + Vite)
    │
    │  GET /api/rooms/<room_id>/status
    │  GET /api/events
    │
backend/ (Flask + SQLite)
    │
    │  POST /api/events
    │
gateway program (Python, reads Pico serial)
    │
    │  USB serial
    │
sensor/ (Raspberry Pi Pico firmware)
    ├── PIR sensor (binary motion trigger)
    ├── mmWave radar RD03D (target tracking)
    └── CO₂ sensor SCD41 (air quality)
```

---

## Folder Structure

```
backend/
├── app/
│   ├── __init__.py       # Application factory: create_app()
│   ├── config.py         # Configuration from .env / defaults
│   ├── database.py       # sqlite3 connection, schema, queries
│   ├── routes.py         # API Blueprint (all HTTP endpoints)
│   └── occupancy.py      # Occupancy count logic + level mapping
├── tests/
│   ├── conftest.py       # pytest fixtures
│   ├── test_health.py    # GET /api/health
│   ├── test_events.py    # POST /api/events
│   └── test_room_status.py # GET status, GET events, POST reset
├── instance/
│   └── occupancy.db      # SQLite database (git-ignored, auto-created)
├── scripts/
│   └── send_test_events.py  # Manual integration test script
├── .env.example          # Environment variable template
├── .gitignore
├── README.md
├── requirements.txt
└── run.py                # Development server entry point
```

---

## Setup

### Docker Compose

From the `Indoor-Occupancy/` directory, start the frontend and backend together:

```bash
docker compose up --build
```

- Dashboard: http://localhost:5173
- API: http://localhost:5001

The SQLite database is retained in the Docker volume `backend-data`. Stop the
services with `docker compose down`; add `-v` only when you intentionally want
to delete the stored database. The hardware serial gateway is not started by
Compose because it needs access to a host serial device.

### Dependencies

- Python 3.11+
- No external database — uses Python's built-in `sqlite3`

---

### WSL Setup (Ubuntu / Debian)

```bash
# 1. Navigate to the backend directory
cd /path/to/Indoor-Occupancy/backend

# 2. Create the virtual environment
python3 -m venv .venv

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Copy the environment file
cp .env.example .env
```

If `python3-venv` is not installed:

```bash
sudo apt update && sudo apt install python3-venv -y
```

---

### Windows PowerShell Setup

```powershell
# 1. Navigate to the backend directory
cd .\backend

# 2. Create the virtual environment
python -m venv .venv

# 3. Activate the virtual environment
.\.venv\Scripts\Activate.ps1

# 4. Install dependencies
pip install -r requirements.txt

# 5. (Optional) Copy the environment file
Copy-Item .env.example .env
```

If PowerShell restricts script execution:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

---

### macOS / Linux Setup

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

---

## Starting the Server

```bash
# From the backend/ directory with the virtual environment active:
python run.py
```

Default URL: **http://localhost:5000**

The SQLite database is created automatically at `instance/occupancy.db` on
first startup.

---

## Running Tests

```bash
# From the backend/ directory with the virtual environment active:
pytest -v
```

All 20 tests should pass.  Tests use a temporary database file that is deleted
after the session completes.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET`  | `/api/health` | Liveness check |
| `POST` | `/api/events` | Ingest a sensor event |
| `GET`  | `/api/events` | List recent events |
| `GET`  | `/api/rooms/<room_id>/status` | Current room occupancy |
| `POST` | `/api/rooms/<room_id>/reset` | Reset room to zero |
| `POST` | `/api/occupancy/events` | Store a PIR doorway occupancy event |
| `GET`  | `/api/occupancy/current` | Current occupancy count |
| `GET`  | `/api/occupancy/events` | List recent PIR events |
| `GET`  | `/api/occupancy/status` | Unified status: occupancy + radar + CO₂ |
| `POST` | `/api/radar/readings` | Store a radar reading |
| `GET`  | `/api/radar/latest` | Latest radar snapshot for all devices |
| `GET`  | `/api/radar/latest/<device_id>` | Latest radar snapshot for one device |
| `POST` | `/api/co2/readings` | Store a CO₂ / environment reading |
| `GET`  | `/api/co2/latest` | Latest environment reading for all devices |
| `GET`  | `/api/co2/latest/<device_id>` | Latest reading for one device |
| `GET`  | `/api/co2/history/<device_id>` | Recent readings history |

---

## curl Examples

### Health check

```bash
curl http://localhost:5000/api/health
```

### Send an ENTRY event

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -d '{"room_id":"room_01","device_id":"door_sensor_01","sensor_type":"mmwave","event_type":"ENTRY","count":1}'
```

### Send an EXIT event

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -d '{"room_id":"room_01","device_id":"door_sensor_01","sensor_type":"mmwave","event_type":"EXIT","count":1}'
```

### Send a PIR trigger

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -d '{"room_id":"room_01","device_id":"pir_out_01","sensor_type":"pir","event_type":"TRIGGER","position":"OUTSIDE","state":1}'
```

### Send an mmWave frame

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -d '{"room_id":"room_01","device_id":"rd03d_01","sensor_type":"mmwave","event_type":"FRAME","target_count":1,"targets":[{"target_id":1,"angle_deg":-6.23,"distance_mm":469.78,"speed_cm_s":0}]}'
```

### Send a CO₂ reading

```bash
curl -X POST http://localhost:5000/api/events \
  -H "Content-Type: application/json" \
  -d '{"room_id":"room_01","device_id":"scd41_01","sensor_type":"co2","event_type":"READING","value":782}'
```

### Get room status

```bash
curl http://localhost:5000/api/rooms/room_01/status
```

### Get recent events

```bash
curl "http://localhost:5000/api/events?room_id=room_01&limit=10"
```

### Filter events by sensor type

```bash
curl "http://localhost:5000/api/events?sensor_type=mmwave&limit=20"
```

### Reset a room

```bash
curl -X POST http://localhost:5000/api/rooms/room_01/reset
```

---

## Test Event Script

Sends a predefined sequence of events and prints results:

```bash
python scripts/send_test_events.py
```

Expected final occupancy count: **2**

Event sequence:
1. ENTRY count=1 → occupancy: 1
2. ENTRY count=2 → occupancy: 3
3. mmWave FRAME (1 target) → occupancy: 3 (no change)
4. PIR TRIGGER → occupancy: 3 (no change)
5. CO₂ READING 750 → occupancy: 3 (no change)
6. EXIT count=1 → occupancy: 2

---

## SQLite Database

The database file is stored at:

```
backend/instance/occupancy.db
```

This file is **git-ignored** and auto-created on first startup.

### Tables

**`sensor_events`** — raw event log (one row per HTTP POST):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `room_id` | TEXT | Room identifier |
| `device_id` | TEXT | Hardware device identifier (optional) |
| `sensor_type` | TEXT | `pir`, `mmwave`, `co2`, etc. |
| `event_type` | TEXT | `ENTRY`, `EXIT`, `TRIGGER`, `FRAME`, `READING`, etc. |
| `value` | REAL | Numeric measurement (optional) |
| `event_count` | INTEGER | Entry/exit count (optional) |
| `payload` | TEXT | Full original JSON body (JSON string) |
| `received_at` | TEXT | UTC ISO 8601 timestamp |

**`room_state`** — current occupancy per room:

| Column | Type | Description |
|--------|------|-------------|
| `room_id` | TEXT | Room identifier (primary key) |
| `occupancy_count` | INTEGER | Current occupancy count |
| `occupancy_level` | TEXT | `Empty`, `Low`, `Medium`, or `High` |
| `last_event` | TEXT | Most recent event type |
| `updated_at` | TEXT | UTC ISO 8601 timestamp of last update |

### Inspect the database

```bash
sqlite3 instance/occupancy.db
```

```sql
SELECT * FROM room_state;
SELECT id, room_id, event_type, received_at FROM sensor_events ORDER BY id DESC LIMIT 10;
```

---

## Room Reset

`POST /api/rooms/<room_id>/reset` sets the occupancy count to zero and records
`last_event = RESET`.

**Historical sensor events are not deleted.**  The full event log is always
preserved for analysis and debugging.  Only the `room_state` record is
modified.

---

## Hardware Gateway Integration

The gateway program (not part of this repository) is responsible for:

1. Opening the Pico USB serial port
2. Parsing sensor output (UART frames)
3. Constructing the JSON event payload
4. Sending an HTTP POST to `http://<backend-host>:5000/api/events`

The Flask backend does not read serial ports or communicate with the Pico
directly.

---

## Occupancy Level Mapping

| Count | Level |
|-------|-------|
| 0 | Empty |
| 1 – 5 | Low |
| 6 – 15 | Medium |
| ≥ 16 | High |

---

## Current Limitations

- **No sensor fusion:** ENTRY/EXIT events must be sent explicitly by the
  gateway program.  PIR and mmWave data is stored but does not automatically
  infer occupancy.
- **No authentication:** The API accepts all requests without any access
  control.  Suitable for local development only.
- **Single machine:** Designed to run on one host (e.g. a laptop or Raspberry
  Pi) alongside the gateway program and frontend.
- **No duplicate filtering:** Repeated events from the same sensor are stored
  as-is.

---

## Future Work

- PIR OUTSIDE → INSIDE sequence detection (entry inference)
- PIR INSIDE → OUTSIDE sequence detection (exit inference)
- mmWave trajectory analysis for occupancy inference
- CO₂ trend analysis as a secondary occupancy signal
- Duplicate-event filtering (debounce repeated triggers)
- Sensor health monitoring (detect stale / offline devices)
- CSV export of event history
- MAE and RMSE evaluation against ground-truth occupancy
- Multi-room visualisation
- Cloud deployment (production hardening)

---

## PIR Doorway Occupancy Events

This section documents the **first backend feature** for receiving and storing
occupancy updates directly from the PIR doorway hardware (Raspberry Pi Pico).

---

### Hardware JSON Format

The Pico firmware sends the following JSON payload for each detected crossing:

**Entry event:**

```json
{
  "device_id": "doorway-pico-01",
  "event_id": 1,
  "event": "entry",
  "count_change": 1,
  "duration_ms": 2404,
  "uptime_ms": 508384
}
```

**Exit event:**

```json
{
  "device_id": "doorway-pico-01",
  "event_id": 2,
  "event": "exit",
  "count_change": -1,
  "duration_ms": 1222,
  "uptime_ms": 496909
}
```

---

### Database Table: `occupancy_events`

Stored at `instance/occupancy.db` alongside the existing tables.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Internal row identifier |
| `device_id` | TEXT | NOT NULL | Hardware device identifier |
| `event_id` | INTEGER | NOT NULL | Monotonic counter from the Pico |
| `event` | TEXT | NOT NULL, `entry` or `exit` | Event direction |
| `count_change` | INTEGER | NOT NULL, `1` or `-1` | Occupancy delta |
| `duration_ms` | INTEGER | NOT NULL, ≥ 0 | Duration of the crossing in milliseconds |
| `uptime_ms` | INTEGER | NOT NULL, ≥ 0 | Device uptime at the time of the event |
| `received_at` | TEXT | NOT NULL | UTC ISO 8601 timestamp (backend-generated) |

**Unique constraint:** `(device_id, event_id)` — prevents the same hardware
event from being stored twice.

---

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/occupancy/events` | Store a PIR doorway occupancy event |
| `GET`  | `/api/occupancy/current` | Current occupancy (sum of `count_change`, ≥ 0) |
| `GET`  | `/api/occupancy/events` | List recent PIR events, newest first |

#### `POST /api/occupancy/events`

Accepts the hardware JSON format, validates all fields, and stores valid events.

**Validation rules:**

- All six fields must be present.
- `event` must be exactly `"entry"` or `"exit"` (lowercase).
- `count_change` must be `1` for `"entry"` and `-1` for `"exit"`.
- `duration_ms` and `uptime_ms` must be integers ≥ 0.
- Duplicate `(device_id, event_id)` pairs are rejected with HTTP 409.

**Success response (HTTP 201):**

```json
{
  "success": true,
  "message": "Occupancy event recorded",
  "data": {
    "device_id": "doorway-pico-01",
    "event_id": 1,
    "event": "entry",
    "count_change": 1
  }
}
```

**Error response (HTTP 400 or 409):**

```json
{
  "error": "Duplicate event: device_id 'doorway-pico-01' and event_id 1 already recorded"
}
```

#### `GET /api/occupancy/current`

Returns the current occupancy calculated from the sum of all stored
`count_change` values.  The value is clamped to zero and will never be
returned as negative.

**Response:**

```json
{
  "occupancy": 3,
  "updated_at": "2026-07-15T21:45:00+00:00"
}
```

#### `GET /api/occupancy/events?limit=20`

Returns the most recent PIR occupancy events.  The `limit` parameter is
optional (default 50, maximum 200).

**Response:**

```json
{
  "events": [
    {
      "id": 2,
      "device_id": "doorway-pico-01",
      "event_id": 2,
      "event": "exit",
      "count_change": -1,
      "duration_ms": 1222,
      "uptime_ms": 496909,
      "received_at": "2026-07-15T21:45:01+00:00"
    }
  ]
}
```

---

### curl Examples — PIR Occupancy

#### Send an entry event

```bash
curl -X POST http://localhost:5000/api/occupancy/events \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "doorway-pico-01",
    "event_id": 1,
    "event": "entry",
    "count_change": 1,
    "duration_ms": 2404,
    "uptime_ms": 508384
  }'
```

#### Send an exit event

```bash
curl -X POST http://localhost:5000/api/occupancy/events \
  -H "Content-Type: application/json" \
  -d '{
    "device_id": "doorway-pico-01",
    "event_id": 2,
    "event": "exit",
    "count_change": -1,
    "duration_ms": 1222,
    "uptime_ms": 496909
  }'
```

#### Get current occupancy

```bash
curl http://localhost:5000/api/occupancy/current
```

#### List recent PIR events

```bash
curl "http://localhost:5000/api/occupancy/events?limit=20"
```

---

### PIR Test Script

The seed script sends six pre-built PIR events and prints the resulting
occupancy without needing the real hardware.

```bash
# Backend must be running first:
python run.py

# In a separate terminal (from the backend/ directory):
python scripts/send_pir_test_events.py
```

Expected output:

```
============================================================
  PIR Doorway Occupancy — Test Event Sender
  Endpoint: http://localhost:5000/api/occupancy/events
============================================================
  event_id=1  entry  →  OK (201)
  event_id=2  entry  →  OK (201)
  event_id=3  entry  →  OK (201)
  event_id=4  exit   →  OK (201)
  event_id=5  entry  →  OK (201)
  event_id=6  exit   →  OK (201)
------------------------------------------------------------
  Current occupancy : 2
  Updated at        : 2026-07-15T21:45:06+00:00
============================================================
  Expected final occupancy: 2
============================================================
```

If the script is run a second time, duplicate events are gracefully skipped
with a 409 response — the occupancy total remains correct.

---

### Running PIR Tests

```bash
# From the backend/ directory with the virtual environment active:
pytest tests/test_occupancy_events.py -v
```

To run the complete test suite (all existing and new tests):

```bash
pytest -v
```

---

### SQLite Database Location

```
backend/instance/occupancy.db
```

This file is git-ignored and is created automatically on first startup.

To inspect the new table:

```bash
sqlite3 instance/occupancy.db
```

```sql
SELECT * FROM occupancy_events ORDER BY id DESC LIMIT 10;
SELECT SUM(count_change) AS occupancy FROM occupancy_events;
```

---

## mmWave Radar Integration

This section documents the radar data pipeline added to complement the PIR
occupancy events.

---

### Hardware Code Location

The Raspberry Pi Pico firmware lives in:

```
sensor/
├── PIR_and_mmWave.py   # Main firmware — PIR logic and radar output
├── rd03d.py            # RD03D mmWave radar driver
└── main.py             # Minimal radar-only test entry point
```

The Pico runs `PIR_and_mmWave.py` and writes JSON lines to stdout via `print()`.
A host PC then reads those lines via USB serial and forwards them to the backend
using `scripts/hardware_gateway.py`.

---

### Hardware JSON Message Formats

The firmware produces two types of JSON messages.

#### Radar message (`message_type: "radar"`)

Emitted every 500 ms (controlled by `RADAR_SEND_INTERVAL_MS = 500`).

```json
{
  "message_type": "radar",
  "device_id": "doorway-pico-01",
  "uptime_ms": 15200,
  "target_count": 1,
  "targets": [
    {
      "target_id": 1,
      "x_mm": 420,
      "y_mm": 1350,
      "distance_mm": 1413.8,
      "angle_deg": 17.3,
      "speed_cm_s": -25
    }
  ]
}
```

- Up to 3 targets per message.
- Targets with all-zero values are filtered out by the firmware before serialisation.

#### Occupancy event message (`message_type: "occupancy_event"`)

Emitted only when a PIR crossing is detected (entry or exit).

```json
{
  "message_type": "occupancy_event",
  "device_id": "doorway-pico-01",
  "event_id": 1,
  "event": "entry",
  "count_change": 1,
  "duration_ms": 820,
  "uptime_ms": 16400,
  "radar": {
    "target_count": 1,
    "targets": []
  }
}
```

- `event_id` is a monotonically incrementing counter per device.
- `count_change` is `1` for `"entry"` and `-1` for `"exit"`.
- The `radar` field contains the most recent radar snapshot at the time of the
  event — stored as a snapshot in `occupancy_events` and not treated as a live
  radar update.

---

### API Endpoints — Summary

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/occupancy/events` | Store a PIR occupancy event (extended with optional `message_type` and `radar`) |
| `GET`  | `/api/occupancy/current` | Current occupancy (sum of `count_change`, ≥ 0) |
| `GET`  | `/api/occupancy/events` | List recent PIR events, newest first |
| `GET`  | `/api/occupancy/status` | Unified status: occupancy + radar + confirmed/uncertain |
| `POST` | `/api/radar/readings` | Store a radar reading |
| `GET`  | `/api/radar/latest` | Latest radar snapshot for all devices |
| `GET`  | `/api/radar/latest/<device_id>` | Latest radar snapshot for one device |

---

### Occupancy Event API — Extended Format

`POST /api/occupancy/events` now accepts the full hardware format including the
optional `message_type` and `radar` fields.

**Backward compatibility:** Requests that omit `message_type` and `radar` are
still accepted — this preserves compatibility with the earlier format.

**Validation rules for new optional fields:**

- If `message_type` is present, it must be `"occupancy_event"`.
- If `radar` is present, it must be an object with:
  - `target_count` (integer, 0–3)
  - `targets` (array whose length equals `target_count`)

---

### Radar API

#### `POST /api/radar/readings`

Accepts a radar message from the gateway and stores it.

**Validation rules:**
- `message_type` must be `"radar"`.
- `device_id` must be a non-empty string.
- `uptime_ms` must be a number ≥ 0.
- `target_count` must be an integer between 0 and 3.
- `targets` must be an array of length equal to `target_count`.
- Each target must contain: `target_id`, `x_mm`, `y_mm`, `distance_mm`,
  `angle_deg`, `speed_cm_s` — all numeric and not boolean.

**Success response (HTTP 201):**

```json
{
  "success": true,
  "message": "Radar reading recorded",
  "data": {
    "device_id": "doorway-pico-01",
    "target_count": 1,
    "received_at": "2026-07-16T02:30:00+00:00"
  }
}
```

#### `GET /api/radar/latest`

Returns the latest radar snapshot for every known device.

```json
{
  "devices": [
    {
      "device_id": "doorway-pico-01",
      "uptime_ms": 15200,
      "target_count": 1,
      "targets": [
        {
          "target_id": 1,
          "x_mm": 420,
          "y_mm": 1350,
          "distance_mm": 1413.8,
          "angle_deg": 17.3,
          "speed_cm_s": -25
        }
      ],
      "received_at": "2026-07-16T02:30:00+00:00"
    }
  ]
}
```

#### `GET /api/radar/latest/<device_id>`

Returns the latest snapshot for a single device.  Returns HTTP 404 if no data
has been received for that device.

---

### Radar Storage Policy

The RD03D radar sends frames continuously.  The firmware throttles output to
once every 500 ms via `RADAR_SEND_INTERVAL_MS`.  Even so, storing every message
permanently would fill the database quickly with redundant data.

The backend therefore uses a two-tier storage policy:

**`radar_latest` table (always updated)**

One row per `device_id`.  Every incoming radar message overwrites the previous
row for that device.  This gives the frontend an always-current snapshot with
no unbounded growth.

**`radar_readings` table (throttled history)**

At most one row per device per second is inserted.  If multiple messages arrive
within one second, only the first is written to history; subsequent messages
still update `radar_latest`.

This keeps the history table small enough for long-term use while still
providing a usable audit trail.

**Occupancy radar snapshots**

The `radar` field inside an `occupancy_event` is stored separately as part of
the `occupancy_events` row (`radar_target_count`, `radar_targets_json`).  It
represents the radar state at the exact moment a PIR crossing was detected and
is independent of the rolling radar stream.

---

### Occupancy Status API

#### `GET /api/occupancy/status`

Returns a unified view of the current occupancy count and radar presence for
use by the frontend dashboard.

**Example response:**

```json
{
  "occupancy": 3,
  "status": "confirmed",
  "radar_presence": true,
  "radar_target_count": 1,
  "last_occupancy_event_at": "2026-07-16T02:25:00+00:00",
  "last_radar_update_at": "2026-07-16T02:29:55+00:00",
  "mismatch_started_at": null
}
```

**Status values:**

| `status` | Meaning |
|---|---|
| `confirmed` | PIR occupancy count and radar presence agree (both zero, or both non-zero). |
| `uncertain` | PIR and radar disagree — see `mismatch_started_at`. |

**mmWave delay handling**

The RD03D radar takes approximately 10 seconds to detect a stationary person
after they enter a room.  This means there will routinely be a brief period
where PIR has detected an entry but radar still shows zero targets.

The backend deliberately does **not** auto-correct the occupancy count based on
radar data.  The `status` field signals the disagreement, and `mismatch_started_at`
records when it began so the frontend can decide how to display it (for example,
showing a warning only after 30 seconds of disagreement).

---

### Hardware Gateway Script

`scripts/hardware_gateway.py` bridges the Pico serial output to the backend.

The Pico writes JSON lines to its USB serial port.  The gateway script reads
those lines and routes each message to the correct backend endpoint.

#### Stdin mode (for testing or piped input)

```bash
# From the backend/ directory with the virtual environment active:
python scripts/hardware_gateway.py --mode stdin

# Simulate a radar message:
echo '{"message_type":"radar","device_id":"doorway-pico-01","uptime_ms":1000,"target_count":0,"targets":[]}' \
    | python scripts/hardware_gateway.py --mode stdin

# Pipe from a file of recorded messages:
python scripts/hardware_gateway.py --mode stdin < recorded_output.jsonl
```

#### Serial mode (live hardware)

```bash
# Linux / macOS:
python scripts/hardware_gateway.py --mode serial --port /dev/ttyACM0 --baudrate 115200

# Windows (check Device Manager for the correct port):
python scripts/hardware_gateway.py --mode serial --port COM3 --baudrate 115200
```

> **Baud rate note:** The Pico's internal UART to the RD03D radar uses 256 000 baud.
> The USB CDC serial port presented to the host PC always runs at 115 200 baud —
> this is what the gateway script connects to.

#### Backend URL

Override the backend URL with `--url` or the `BACKEND_URL` environment variable:

```bash
# Via argument:
python scripts/hardware_gateway.py --mode stdin --url http://192.168.1.10:5000

# Via environment variable:
export BACKEND_URL=http://192.168.1.10:5000
python scripts/hardware_gateway.py --mode stdin
```

The default is `http://localhost:5000`.

---

### Radar Test Data Script

`scripts/send_radar_test_data.py` sends a set of pre-built test payloads to the
backend without needing real hardware.

```bash
# Backend must be running first:
python run.py

# In a separate terminal (from the backend/ directory):
python scripts/send_radar_test_data.py
```

The script covers:
- Radar with 0, 1, and 3 targets
- Occupancy entry and exit events with radar snapshots
- Backward-compatible format (no `message_type` or `radar`)
- Invalid payloads that should be rejected (to confirm validation works)
- Querying all status endpoints

---

### curl Examples — Radar and Status

#### Send a radar reading

```bash
curl -X POST http://localhost:5000/api/radar/readings \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "radar",
    "device_id": "doorway-pico-01",
    "uptime_ms": 15200,
    "target_count": 1,
    "targets": [
      {"target_id": 1, "x_mm": 420, "y_mm": 1350,
       "distance_mm": 1413.8, "angle_deg": 17.3, "speed_cm_s": -25}
    ]
  }'
```

#### Get latest radar for all devices

```bash
curl http://localhost:5000/api/radar/latest
```

#### Get latest radar for one device

```bash
curl http://localhost:5000/api/radar/latest/doorway-pico-01
```

#### Send a PIR occupancy event (new full format)

```bash
curl -X POST http://localhost:5000/api/occupancy/events \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "occupancy_event",
    "device_id": "doorway-pico-01",
    "event_id": 1,
    "event": "entry",
    "count_change": 1,
    "duration_ms": 820,
    "uptime_ms": 16400,
    "radar": {"target_count": 0, "targets": []}
  }'
```

#### Get unified occupancy status

```bash
curl http://localhost:5000/api/occupancy/status
```

---

### Running the Full Test Suite

```bash
# From the backend/ directory with the virtual environment active:
pytest -v
```

All 165 tests should pass.  The test suite includes:
- All pre-existing tests (sensor events, room state, PIR occupancy)
- New radar endpoint tests (`test_radar.py`)
- New occupancy status tests (`test_occupancy_status.py`)
- Gateway unit tests (`test_gateway.py`)
- Extended occupancy event tests (message_type, radar snapshot, backward compat)
- Environment / CO₂ endpoint tests (`test_environment.py`)
- CO₂ fields in occupancy status tests

New test files use function-scoped database fixtures so every test runs in full
isolation regardless of order.

---

### SQLite Database — New Tables

**`radar_latest`** — current radar snapshot per device:

| Column | Type | Description |
|--------|------|-------------|
| `device_id` | TEXT PRIMARY KEY | Hardware device identifier |
| `uptime_ms` | INTEGER | Device uptime at time of reading |
| `target_count` | INTEGER | Number of detected targets |
| `targets_json` | TEXT | JSON array of target objects |
| `received_at` | TEXT | UTC ISO 8601 timestamp (backend-generated) |

**`radar_readings`** — throttled radar history (at most 1 row/device/second):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `device_id` | TEXT | Hardware device identifier |
| `uptime_ms` | INTEGER | Device uptime at time of reading |
| `target_count` | INTEGER | Number of detected targets |
| `targets_json` | TEXT | JSON array of target objects |
| `received_at` | TEXT | UTC ISO 8601 timestamp |

**`occupancy_events`** — extended with three new columns (safe migration applied
on startup; existing data is preserved):

| Column | Type | Description |
|--------|------|-------------|
| `message_type` | TEXT | `"occupancy_event"` if present in the hardware JSON |
| `radar_target_count` | INTEGER | Target count from the embedded radar snapshot |
| `radar_targets_json` | TEXT | JSON array of targets from the embedded radar snapshot |

---

## CO₂ / Environment Sensor Integration

This section documents the environment sensor (SCD41) data pipeline — CO₂,
temperature, and humidity readings.

---

### Hardware JSON Format

The CO₂ sensor sends the following JSON payload approximately every 5 seconds:

```json
{
  "message_type": "environment",
  "device_id": "scd41-nano-01",
  "uptime_ms": 7080308,
  "co2_ppm": 1520,
  "temperature_c": 21.4,
  "humidity_percent": 64.6
}
```

- `co2_ppm` is the primary signal for occupancy estimation.
- `temperature_c` and `humidity_percent` are stored as supplementary data.
- The sensor outputs one reading every **5 seconds**.

---

### API Endpoints — Environment

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/co2/readings` | Accept and store a CO₂ / environment reading |
| `GET`  | `/api/co2/latest` | Latest reading for all environment devices |
| `GET`  | `/api/co2/latest/<device_id>` | Latest reading for one device |
| `GET`  | `/api/co2/history/<device_id>` | Recent readings history for trend analysis |

#### `POST /api/co2/readings`

Accepts an environment reading from the hardware (via the gateway script).

**Validation rules:**
- `message_type` must be `"environment"`.
- `device_id` must be a non-empty string.
- `uptime_ms` must be a number ≥ 0.
- `co2_ppm` must be a number ≥ 0.
- `temperature_c` must be a number.
- `humidity_percent` must be a number between 0 and 100.

**Success response (HTTP 201):**

```json
{
  "success": true,
  "message": "Environment reading recorded",
  "data": {
    "device_id": "scd41-nano-01",
    "co2_ppm": 1520,
    "temperature_c": 21.4,
    "humidity_percent": 64.6,
    "received_at": "2026-07-19T02:00:00+00:00"
  }
}
```

#### `GET /api/co2/latest`

Returns the latest environment reading for every known device.

```json
{
  "devices": [
    {
      "device_id": "scd41-nano-01",
      "uptime_ms": 7080308,
      "co2_ppm": 1520,
      "temperature_c": 21.4,
      "humidity_percent": 64.6,
      "received_at": "2026-07-19T02:00:00+00:00"
    }
  ]
}
```

#### `GET /api/co2/latest/<device_id>`

Returns the latest reading for a single device.  Returns HTTP 404 if no data
has been received for that device.

#### `GET /api/co2/history/<device_id>?limit=50`

Returns recent environment readings for a device, newest first.  The `limit`
parameter is optional (default 50, maximum 200).

```json
{
  "device_id": "scd41-nano-01",
  "readings": [
    {
      "id": 3,
      "device_id": "scd41-nano-01",
      "uptime_ms": 7090000,
      "co2_ppm": 1200,
      "temperature_c": 22.0,
      "humidity_percent": 58.0,
      "received_at": "2026-07-19T02:00:15+00:00"
    }
  ]
}
```

---

### Environment Storage Policy

The SCD41 sensor sends readings every 5 seconds.  The backend uses a two-tier
storage policy identical in pattern to the radar pipeline:

**`environment_latest` table (always updated)**

One row per `device_id`.  Every incoming reading overwrites the previous row
for that device.  This gives the frontend an always-current snapshot.

**`environment_readings` table (throttled history)**

At most one row per device per 5 seconds is inserted.  This matches the
sensor's measurement interval and prevents unbounded database growth.

---

### CO₂ Level Classification

The unified status endpoint classifies CO₂ readings using ASHRAE-based
thresholds:

| CO₂ (ppm) | Level | Interpretation |
|-----------|-------|----------------|
| < 800 | `normal` | Typical outdoor / empty room |
| 800 – 1500 | `elevated` | Suggests people are present |
| > 1500 | `high` | Multiple people or poor ventilation |

> **Note:** CO₂ data is a supplementary occupancy signal.  It does not
> directly change the occupancy count — only PIR events modify the count.
> The CO₂ level appears in the `GET /api/occupancy/status` response alongside
> the PIR count and radar presence.

---

### Enhanced Occupancy Status Response

`GET /api/occupancy/status` now includes environment data:

```json
{
  "occupancy": 3,
  "status": "confirmed",
  "radar_presence": true,
  "radar_target_count": 1,
  "co2_ppm": 1520,
  "co2_level": "high",
  "temperature_c": 21.4,
  "humidity_percent": 64.6,
  "last_occupancy_event_at": "2026-07-19T01:55:00+00:00",
  "last_radar_update_at": "2026-07-19T01:59:55+00:00",
  "last_environment_update_at": "2026-07-19T02:00:00+00:00",
  "mismatch_started_at": null
}
```

When no environment data has been received, `co2_ppm`, `co2_level`,
`temperature_c`, `humidity_percent`, and `last_environment_update_at` are `null`.

---

### curl Examples — Environment

#### Send a CO₂ reading

```bash
curl -X POST http://localhost:5000/api/co2/readings \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "environment",
    "device_id": "scd41-nano-01",
    "uptime_ms": 7080308,
    "co2_ppm": 1520,
    "temperature_c": 21.4,
    "humidity_percent": 64.6
  }'
```

#### Get latest environment for all devices

```bash
curl http://localhost:5000/api/co2/latest
```

#### Get latest for one device

```bash
curl http://localhost:5000/api/co2/latest/scd41-nano-01
```

#### Get history for a device

```bash
curl "http://localhost:5000/api/co2/history/scd41-nano-01?limit=20"
```

#### Get unified status (now includes CO₂)

```bash
curl http://localhost:5000/api/occupancy/status
```

---

### Environment Test Data Script

`scripts/send_environment_test_data.py` sends simulated CO₂ readings to the
backend without needing real hardware.

```bash
# Backend must be running first:
python run.py

# In a separate terminal (from the backend/ directory):
python scripts/send_environment_test_data.py
```

The script covers:
- Increasing CO₂ readings (empty room → crowded → clearing)
- Invalid payloads that should be rejected
- Multi-device data
- Querying latest, history, and unified status endpoints

---

### SQLite Database — Environment Tables

**`environment_latest`** — current environment reading per device:

| Column | Type | Description |
|--------|------|-------------|
| `device_id` | TEXT PRIMARY KEY | Hardware device identifier |
| `uptime_ms` | INTEGER | Device uptime at time of reading |
| `co2_ppm` | INTEGER | CO₂ concentration in parts per million |
| `temperature_c` | REAL | Temperature in degrees Celsius |
| `humidity_percent` | REAL | Relative humidity percentage |
| `received_at` | TEXT | UTC ISO 8601 timestamp (backend-generated) |

**`environment_readings`** — throttled history (at most 1 row/device/5 seconds):

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER | Auto-increment primary key |
| `device_id` | TEXT | Hardware device identifier |
| `uptime_ms` | INTEGER | Device uptime at time of reading |
| `co2_ppm` | INTEGER | CO₂ concentration |
| `temperature_c` | REAL | Temperature |
| `humidity_percent` | REAL | Humidity |
| `received_at` | TEXT | UTC ISO 8601 timestamp |
