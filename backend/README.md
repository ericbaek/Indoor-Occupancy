# Indoor Occupancy Backend

Flask and SQLite backend for PIR, mmWave radar, SCD41 CO₂, BLE signal heatmap, reports and predictive occupancy.

## Setup

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

macOS or Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

The default port is `5000`.

```powershell
$env:FLASK_PORT = "5001"
$env:FLASK_DEBUG = "false"
.\.venv\Scripts\python.exe .\run.py
```

Health check:

```text
GET http://127.0.0.1:5001/api/health
```

The backend terminal also accepts manual occupancy commands:

- `ADD`
- `REMOVE`
- `SET 5`
- `SHOW`
- `STOP`

## Hardware gateway

The gateway reads one JSON object per serial line and forwards it to the matching API.

```powershell
.\.venv\Scripts\python.exe .\scripts\hardware_gateway.py `
  --mode serial `
  --port COM5 `
  --baudrate 115200 `
  --url "http://127.0.0.1:5001"
```

SCD41 message:

```json
{"message_type":"environment","device_id":"scd41-nano-01","uptime_ms":5000,"co2_ppm":491,"temperature_c":23.6,"humidity_percent":37.9}
```

PIR message:

```json
{"message_type":"occupancy_event","device_id":"pir-door-01","event_id":1,"event":"entry","count_change":1,"duration_ms":650,"uptime_ms":5000}
```

Radar message:

```json
{"message_type":"radar","device_id":"rd03d-01","uptime_ms":5000,"target_count":1,"targets":[{"target_id":1,"x_mm":300,"y_mm":1368,"angle_deg":12.5,"distance_mm":1400,"speed_cm_s":8.0}]}
```

BLE scanners run natively on the left and right computers. See [`../NATIVE_BLUETOOTH.md`](../NATIVE_BLUETOOTH.md).

## APIs

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Backend and database health |
| POST | `/api/events` | Generic sensor event |
| GET | `/api/events` | Recent generic events |
| GET | `/api/rooms/<room_id>/status` | Current room state |
| POST | `/api/rooms/<room_id>/reset` | Reset a room |
| POST | `/api/occupancy/events` | PIR occupancy event |
| POST | `/api/occupancy/calibrate` | Manual occupancy adjustment |
| GET | `/api/occupancy/current` | Current occupancy |
| GET | `/api/occupancy/events` | Occupancy event history |
| GET | `/api/occupancy/status` | Fused dashboard status |
| POST | `/api/radar/readings` | Radar reading |
| GET | `/api/radar/latest` | Latest radar readings |
| POST | `/api/co2/readings` | CO₂ reading |
| GET | `/api/co2/latest` | Latest CO₂ readings |
| GET | `/api/co2/history/<device_id>` | CO₂ history |
| POST | `/api/bluetooth/signals` | BLE anchor reading |
| GET | `/api/bluetooth/signal-strength` | Left/right signal heatmap data |
| GET | `/api/reports/summary` | Report summary |
| GET | `/api/reports/evaluation` | Evaluation metrics |
| GET | `/api/reports/exports` | Available exports |
| GET | `/api/reports/exports/<id>/download` | CSV export |
| GET | `/api/ml/health` | ML service health |
| GET | `/api/ml/metadata` | Model metadata |
| GET | `/api/ml/metrics` | Model metrics |
| POST | `/api/ml/predict` | Prediction from supplied features |
| POST | `/api/ml/predict/live` | Prediction from recent sensor data |
| GET | `/api/ml/predictions/latest` | Latest stored prediction |
| GET | `/api/ml/live/status` | Live prediction scheduler status |

## Database

SQLite tables are created on startup:

- `sensor_events`
- `room_state`
- `occupancy_events`
- `radar_latest`
- `radar_readings`
- `environment_latest`
- `environment_readings`
- `bluetooth_readings`
- `occupancy_ground_truth`
- `ml_predictions`

The database path is controlled by `DATABASE_PATH`. The default is `instance/occupancy.db` relative to the working directory.

## Tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Test senders are in `backend/scripts` for PIR, radar and CO₂ payloads.
