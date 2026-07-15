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

