# Room Sense — Indoor Occupancy Intelligence

Room Sense is a full-stack indoor occupancy monitoring and forecasting system for sensor-instrumented rooms and doorways. It collects live events from PIR and mmWave radar sensors, environmental readings from an SCD41 CO₂ sensor, and relative Bluetooth signal strength from two anchor computers. The data is stored in SQLite, exposed through a Flask API, and presented in a React dashboard.

## What this project does

The system helps an operator answer four practical questions:

1. **How many people are currently in the monitored space?** PIR entry/exit events maintain the occupancy count. The mmWave radar independently reports live target presence and up to three tracked targets.
2. **Can the current reading be trusted?** The backend compares the PIR-derived count with radar presence and reports the state as `confirmed` when they agree or `uncertain` when they disagree.
3. **What is the current room environment?** SCD41 readings provide CO₂ concentration, temperature, and humidity, with CO₂ classified as normal, elevated, or high.
4. **What may happen next?** When a trained model is available, five-minute sensor windows are used to produce a 30-minute occupancy forecast, an occupancy interval, overcrowding risk, ventilation guidance, empty-room probabilities, and a relative BLE activity side.

The dashboard brings these signals together into a single operator view with live statistics, occupancy history, a radar scope, a CO₂ chart, approximate left/right BLE activity, predictive occupancy, report summaries, evaluation metrics, and downloadable CSV/PDF exports.

This is a doorway-oriented sensing system rather than a general multi-room people-counting platform. The current `Rooms` and `Alerts` views contain frontend demonstration data, while the live dashboard, sensor status, reports, and ML views are backed by the Flask service. BLE is deliberately treated as a relative signal-strength indicator: it does **not** count people or devices and does **not** calculate distance or coordinates.

## System overview

```text
 PIR + mmWave firmware ─┐
 SCD41 firmware ────────┼─> USB serial ─> hardware_gateway.py ─┐
                       │                                      │
 BLE anchor computer ──┴─> ble_scanner.py ────────────────────┤
                                                              v
                                                    Flask REST API
                                                              │
                                                              v
                                                   SQLite occupancy.db
                                                              │
                                      ┌────────────────────────┴────────────────────────┐
                                      v                                                 v
                              React + Vite dashboard                         ML live scheduler
                              localhost:5173                                 30-minute forecasts
```

The native Bluetooth deployment uses two computers: a main computer running the backend, frontend, and `left-anchor` scanner, plus a second computer running the `right-anchor` scanner. See [`NATIVE_BLUETOOTH.md`](NATIVE_BLUETOOTH.md) for the complete two-computer setup.

## Main capabilities

| Area | What is implemented |
| --- | --- |
| Occupancy | PIR entry/exit ingestion, duplicate-event protection, non-negative count clamping, manual calibration, recent-event history |
| Radar | Latest snapshot and historical readings, up to three targets per reading, target coordinates, distance, angle, and speed |
| Sensor fusion | PIR-versus-radar agreement status and mismatch duration for operator review |
| Environment | SCD41 CO₂, temperature, and humidity ingestion, latest values, history, and CO₂ bands |
| Bluetooth | Two-anchor BLE scan windows, RSSI normalization, exponential moving average smoothing, calibration offsets, active/offline status, and relative stronger-side detection |
| Dashboard | Live occupancy cards, time-range charts, radar scope, CO₂ trend, sensor health, BLE heatmap, and ML forecast panel |
| Reports | 24-hour, 7-day, 30-day, and 90-day summaries; fusion evaluation metrics; CSV/PDF downloads |
| Predictive ML | Occupancy regression, ventilation classification/rules, overcrowding risk, empty-room probabilities, input-quality warnings, and dry-run recommendations |
| Hardware integration | Newline-delimited JSON over serial, with routing by `message_type` to the relevant API endpoint |

## Technology stack

- **Frontend:** React 19, TypeScript, Vite, Recharts, Lucide React, Vitest, Oxlint
- **Backend:** Python 3.12, Flask, Flask-CORS, SQLite
- **Data and ML:** pandas, scikit-learn, joblib, openpyxl
- **Hardware communication:** `pyserial`, Bleak, MicroPython/Arduino firmware
- **Local orchestration:** Docker Compose or native PowerShell/Terminal processes

## Repository layout

```text
.
├── backend/
│   ├── app/                       Flask application, API routes, SQLite access, BLE service
│   ├── ml/                        Feature engineering, training, prediction, safety, scheduling
│   ├── scripts/                   Serial gateway, BLE scanner, test senders, report seeder
│   ├── tests/                     Backend unit and API tests
│   ├── models/predictive_occupancy/  Local ML artefacts (ignored by Git)
│   ├── requirements.txt
│   └── README.md                  Backend-specific notes
├── frontend/
│   ├── src/components/            Dashboard cards, charts, radar, BLE, and sensor views
│   ├── src/pages/                 Reports and settings pages
│   ├── src/hooks/                 API polling, ML, reports, preferences, and calibration
│   ├── package.json
│   └── README.md                  Frontend-specific notes
├── sensor/                        MicroPython sensor firmware and SCD41 Arduino sketch
├── hardware/                      BLE tag Arduino sketch
├── compose.yaml                   Backend and frontend Docker services
├── run_main_windows.ps1           Native Windows launcher for backend/frontend/left scanner
├── run_right_anchor_windows.ps1   Native Windows launcher for the right BLE scanner
├── run_demo_windows.ps1           Backend launcher that resets its local database first
├── NATIVE_BLUETOOTH.md             Full native two-computer Bluetooth instructions
└── README.md
```

## Prerequisites

For the software-only dashboard:

- Docker Desktop with Docker Compose, **or**
- Python 3.12 or later and Node.js 22 or later

For live hardware:

- A microcontroller running the firmware in `sensor/` for PIR, mmWave, and/or SCD41 data
- A USB serial connection visible to the host running `hardware_gateway.py`
- Bluetooth permission for each computer running `ble_scanner.py`
- A BLE tag or other permitted Bluetooth source for relative signal testing

## Quick start with Docker

1. From the repository root, start both services:

   ```bash
   docker compose up --build
   ```

2. Open the dashboard at [`http://localhost:5173`](http://localhost:5173).

3. Check the backend:

   ```bash
   curl http://localhost:5001/api/health
   ```

The backend is published on host port `5001` and the frontend on host port `5173`. The frontend API URL is injected by `compose.yaml`. If `172.20.10.2` is not the correct address for your environment, set the frontend service's `VITE_API_BASE_URL` to `http://localhost:5001/api` for a local-only browser, or to the main computer's reachable LAN address for remote clients, then restart Compose.

The Compose database is persisted in the `backend-data` volume. The frontend uses a separate volume for `node_modules`.

## Native development setup

### Backend

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe .\run.py
```

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

The backend listens on `http://localhost:5000` by default and creates `instance/occupancy.db` on startup. A basic health check is:

```text
GET http://localhost:5000/api/health
```

To run on another port, set `FLASK_PORT` before starting the server. To avoid the Flask development reloader during local testing, set `FLASK_DEBUG=false`.

### Frontend

In a second terminal:

```bash
cd frontend
npm ci
```

Set the API base URL to match the backend, then start Vite:

```powershell
# Windows PowerShell
$env:VITE_API_BASE_URL = "http://127.0.0.1:5000/api"
npm run dev -- --host 0.0.0.0
```

```bash
# macOS/Linux
export VITE_API_BASE_URL=http://127.0.0.1:5000/api
npm run dev -- --host 0.0.0.0
```

Open [`http://localhost:5173`](http://localhost:5173). The dashboard polls the backend for live data. If the backend is unavailable, the UI shows an availability message and retains the last known state where possible.

### Windows one-command native launcher

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_main_windows.ps1
```

This creates missing local dependencies and opens separate PowerShell windows for the backend, frontend, and `left-anchor` BLE scanner. It does not start a physical sensor gateway; connect one separately using the command below.

The `run_demo_windows.ps1` script is different: it starts the backend after removing the local SQLite database files. Use its `-WhatIf` option to inspect the planned reset before running it. Existing local data in that database is not preserved by the reset.

## Feeding sensor data

### Serial hardware gateway

The gateway reads one JSON object per serial line and routes it according to `message_type`:

| `message_type` | API route |
| --- | --- |
| `occupancy_event` | `POST /api/occupancy/events` |
| `radar` | `POST /api/radar/readings` |
| `environment` | `POST /api/co2/readings` |

Example for a Windows serial port:

```powershell
cd backend
.\.venv\Scripts\python.exe .\scripts\hardware_gateway.py `
  --mode serial `
  --port COM5 `
  --baudrate 115200 `
  --url http://127.0.0.1:5000
```

The gateway can also read newline-delimited JSON from standard input:

```bash
python backend/scripts/hardware_gateway.py --mode stdin --url http://127.0.0.1:5000
```

### Example payloads

Occupancy event:

```json
{
  "message_type": "occupancy_event",
  "device_id": "doorway-pico-01",
  "event_id": 1000001,
  "event": "entry",
  "count_change": 1,
  "duration_ms": 650,
  "uptime_ms": 5000
}
```

Radar snapshot:

```json
{
  "message_type": "radar",
  "device_id": "rd03d-01",
  "uptime_ms": 5000,
  "target_count": 1,
  "targets": [
    {
      "target_id": 1,
      "x_mm": 300,
      "y_mm": 1368,
      "angle_deg": 12.5,
      "distance_mm": 1400,
      "speed_cm_s": 8.0
    }
  ]
}
```

SCD41 environment reading:

```json
{
  "message_type": "environment",
  "device_id": "scd41-nano-01",
  "uptime_ms": 5000,
  "co2_ppm": 491,
  "temperature_c": 23.6,
  "humidity_percent": 37.9
}
```

The backend validates payload types and ranges, rejects malformed messages, prevents duplicate occupancy events using `(device_id, event_id)`, and stores both latest snapshots and throttled historical readings.

### Test senders without hardware

With the native backend running on port `5000`, use the included senders:

```bash
cd backend
python scripts/send_pir_test_events.py
python scripts/send_radar_test_data.py
python scripts/send_environment_test_data.py --url http://localhost:5000
```

The report page can be populated with reproducible demonstration history:

```bash
cd backend
python scripts/seed_reports_demo_data.py --db instance/occupancy.db --days 7 --seed 42
```

These scripts write test data to the configured local database. They are useful for validating the dashboard and API flow, not for calibrating a real deployment.

## Native two-anchor Bluetooth setup

The BLE scanner collects short scan windows, keeps the strongest observed signals, converts RSSI to a `0–100` score, and posts one summary to the backend. The backend applies calibration and smoothing before exposing the left/right summary to the dashboard.

Start the main computer's backend and frontend first. Then start the left scanner locally and the right scanner on the second computer. On Windows, the launchers are:

```powershell
# Main computer
powershell -ExecutionPolicy Bypass -File .\run_main_windows.ps1

# Right computer; replace the address with the main computer's LAN IPv4 address
powershell -ExecutionPolicy Bypass -File .\run_right_anchor_windows.ps1 -MainIp 192.168.1.220
```

For macOS, Linux, manual commands, Bluetooth permissions, calibration, and troubleshooting, follow [`NATIVE_BLUETOOTH.md`](NATIVE_BLUETOOTH.md).

Important interpretation limits:

- BLE signal strength is relative and environment-dependent.
- The scanner does not send a device count to the backend.
- The heatmap indicates the stronger side, not a precise location.
- An anchor is considered offline after approximately 15 seconds without a report.

## Predictive occupancy and ML

The ML service uses recent sensor data aggregated into a five-minute window. It can expose:

- 30-minute predicted occupancy with a prediction interval and confidence score
- Overcrowding probability and capacity warning
- Recommended ventilation level (`OFF`, `LOW`, `MEDIUM`, or `HIGH`)
- Empty-room probabilities at 30 and 60 minutes
- Relative BLE activity side (`LEFT`, `RIGHT`, `BALANCED`, or `NO_SIGNAL`)
- Input-quality warnings when expected sensor features are missing or stale

Predictions and recommendations are explicitly **dry-run only**. The service records recommendations for auditability but does not send commands to ventilation hardware.

### Model availability

Model binaries and generated metadata are intentionally excluded from Git under `backend/models/predictive_occupancy/`. A fresh checkout therefore starts without a trained model. Until a model bundle is generated, ML health/prediction endpoints report that the model is unavailable and the dashboard waits for a prediction.

### Training a model

The training dataset must be supplied separately as an `.xlsx` or `.csv` file. The loader validates the required timestamps, sensor features, ground-truth columns, and future target columns before training. From `backend/`:

```bash
python -m ml.train \
  --dataset /path/to/dataset.xlsx \
  --output-dir models/predictive_occupancy \
  --room-capacity 30
```

Training performs chronological train/validation/test splitting, feature preprocessing, candidate model comparison, baseline comparison, leakage checks, safety checks, and writes:

- `model_bundle.joblib`
- `metadata.json`
- `training_config.json`
- `feature_names.json`
- `metrics.json`

The training configuration currently uses Australia/Sydney timestamps and a default 30-person room capacity. Adjust the runtime configuration when deploying to a different room or schedule.

For live ML BLE features, make sure `ML_BLE_LEFT_SCANNER_ID` and `ML_BLE_RIGHT_SCANNER_ID` match the actual scanner identifiers sent by the BLE service. The BLE ingestion defaults are `left-anchor` and `right-anchor`.

## API reference

All application endpoints are prefixed with `/api`.

### Health and occupancy

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Backend and database health |
| `POST` | `/events` | Store a generic room sensor event |
| `GET` | `/events` | List recent generic events; supports room/sensor/event filters |
| `GET` | `/rooms/<room_id>/status` | Read a room's current state |
| `POST` | `/rooms/<room_id>/reset` | Reset room occupancy to zero |
| `POST` | `/occupancy/events` | Store a validated PIR/radar occupancy event |
| `GET` | `/occupancy/current` | Read the current occupancy total |
| `POST` | `/occupancy/calibrate` | Apply an absolute occupancy or delta calibration |
| `GET` | `/occupancy/events` | List recent occupancy events |
| `GET` | `/occupancy/status` | Return combined occupancy, radar, CO₂, and mismatch status |

Example:

```bash
curl http://localhost:5000/api/occupancy/status
```

### Radar, CO₂, and Bluetooth

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `POST` | `/radar/readings` | Store a radar snapshot with 0–3 targets |
| `GET` | `/radar/latest` | Read the latest snapshot for all radar devices |
| `GET` | `/radar/latest/<device_id>` | Read one radar device's latest snapshot |
| `POST` | `/co2/readings` | Store an SCD41 environment reading |
| `GET` | `/co2/latest` | Read the latest environment reading for all devices |
| `GET` | `/co2/latest/<device_id>` | Read one device's latest environment reading |
| `GET` | `/co2/history/<device_id>` | Read recent CO₂ history |
| `POST` | `/bluetooth/signals` | Store a left/right BLE anchor summary |
| `POST` | `/bluetooth/readings` | Compatibility alias for Bluetooth signal ingestion |
| `GET` | `/bluetooth/signal-strength` | Read the smoothed two-zone signal summary |
| `GET` | `/bluetooth/zones` | Compatibility alias for the same summary |

### Reports

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/reports/summary?range=24h\|7d\|30d\|90d` | Summary statistics and data completeness |
| `GET` | `/reports/evaluation?range=...` | Fusion metrics against logged ground truth |
| `GET` | `/reports/exports?range=...` | List available CSV/PDF exports |
| `GET` | `/reports/exports/<id>/download?range=...` | Download a generated report |

### ML

| Method | Endpoint | Purpose |
| --- | --- | --- |
| `GET` | `/ml/health` | Model readiness and endpoint metadata |
| `GET` | `/ml/metadata` | Model metadata and feature contract |
| `GET` | `/ml/metrics` | Training and evaluation metrics |
| `POST` | `/ml/predict` | Predict from a supplied sensor window |
| `POST` | `/ml/recommendations/dry-run` | Generate and audit a dry-run recommendation |
| `GET` | `/ml/recommendations/history` | Read recent recommendation history |
| `POST` | `/ml/predict/live` | Aggregate current readings and run a prediction |
| `GET` | `/ml/predictions/latest` | Read the latest stored live prediction |
| `GET` | `/ml/predictions` | Read live prediction history |
| `GET` | `/ml/sensor-window/latest` | Inspect the latest aggregated feature window |
| `GET` | `/ml/live/status` | Read scheduler status and last prediction information |

## Configuration

Copy `backend/.env.example` to a local environment file if desired. The application reads environment variables at startup.

### Backend and reporting

| Variable | Default | Description |
| --- | --- | --- |
| `FLASK_HOST` | `0.0.0.0` | Bind address |
| `FLASK_PORT` | `5000` | Backend port |
| `FLASK_DEBUG` | `true` | Flask development mode; use `false` outside local development |
| `DATABASE_PATH` | `instance/occupancy.db` | SQLite database path |
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:5173` | Comma-separated allowed browser origins |
| `REPORT_ROOM_ID` | `K17-101` | Room label used in report exports |
| `REPORT_TIMEZONE` | `Australia/Sydney` | Report display timezone |
| `VITE_API_BASE_URL` | `http://localhost:5000/api` | Frontend API base URL, set when starting Vite |

### Bluetooth

| Variable | Default | Description |
| --- | --- | --- |
| `ANCHOR_ID` | unset | Required scanner ID: `left-anchor` or `right-anchor` |
| `BACKEND_URL` | unset for scanner | Full Bluetooth ingestion URL, normally `http://<host>:5000/api/bluetooth/signals` |
| `BLE_SCAN_WINDOW_SECONDS` | `4` | Scanner aggregation window |
| `BLE_STRONGEST_SIGNAL_COUNT` | `3` | Number of strongest RSSI groups retained per window |
| `BLE_MINIMUM_RSSI` | `-100` | Lower RSSI bound for score normalization |
| `BLE_MAXIMUM_RSSI` | `-40` | Upper RSSI bound for score normalization |
| `BLE_LEFT_RSSI_OFFSET` | `0` | Backend calibration offset for the left anchor |
| `BLE_RIGHT_RSSI_OFFSET` | `0` | Backend calibration offset for the right anchor |
| `BLE_EMA_ALPHA` | `0.3` | Smoothing factor for signal scores |
| `BLE_ANCHOR_TIMEOUT_SECONDS` | `15` | Time before an anchor is marked offline |
| `BLE_BALANCED_THRESHOLD` | `2` | Score difference treated as balanced |

### Live ML

| Variable | Default | Description |
| --- | --- | --- |
| `ML_MODEL_DIR` | `backend/models/predictive_occupancy` | Directory containing the trained model bundle |
| `ML_LIVE_PREDICTION_ENABLED` | `true` | Enable the background prediction scheduler |
| `ML_LIVE_PREDICTION_INTERVAL_SECONDS` | `300` | Scheduler interval |
| `ML_SENSOR_WINDOW_SECONDS` | `300` | Sensor aggregation window |
| `ML_ROOM_OPEN_HOUR` | `9` | Room opening hour used by feature engineering |
| `ML_ROOM_OPERATING_MINUTES` | `480` | Operating duration used by feature engineering |
| `ML_DEFAULT_VENTILATION` | `OFF` | Current ventilation state when no external state is available |
| `ML_MINIMUM_VENTILATION` | `OFF` | Safety lower bound for recommendations |
| `ML_MAXIMUM_VENTILATION` | `HIGH` | Safety upper bound for recommendations |
| `ML_RADAR_EXPECTED_INTERVAL_SECONDS` | `1` | Expected radar cadence |
| `ML_CO2_EXPECTED_INTERVAL_SECONDS` | `5` | Expected CO₂ cadence |
| `ML_RADAR_STALE_SECONDS` | `15` | Radar staleness threshold |
| `ML_CO2_STALE_SECONDS` | `15` | CO₂ staleness threshold |
| `ML_BLE_LEFT_SCANNER_ID` | `anchor-left` | Identifier used by ML aggregation for the left scanner |
| `ML_BLE_RIGHT_SCANNER_ID` | `anchor-right` | Identifier used by ML aggregation for the right scanner |
| `ML_BLE_SWITCH_THRESHOLD_DB` | `5` | RSSI difference used for ML stronger-side classification |

## Testing and quality checks

Backend tests:

```bash
cd backend
python -m pytest -q
```

Frontend checks:

```bash
cd frontend
npm test
npm run lint
npm run build
```

The backend test suite covers API validation, room and occupancy state, radar, environment readings, BLE scanning/service logic, hardware gateway routing, ML feature engineering, leakage checks, safety logic, live predictions, and report-related behavior. The frontend suite covers charts, radar rendering, polling hooks, and keyboard calibration behavior.

## Operational notes and limitations

- The default server is Flask's development server. Add authentication, production serving, access control, and a managed database before exposing the API beyond a trusted local network.
- `SECRET_KEY` defaults to a development value and should be overridden in any deployment that relies on Flask session or security features.
- SQLite is appropriate for a local prototype and single-room deployment; a multi-room or high-ingestion deployment may require a server database and retention policy.
- The occupancy count is event-based and can drift if a doorway event is missed. Use the calibration endpoint or terminal controls (`ADD`, `REMOVE`, `SET <n>`, `SHOW`, `STOP`) when appropriate.
- CO₂ is a delayed contextual signal, not a direct people counter. Radar presence also indicates detected targets, not guaranteed unique people over time.
- BLE RSSI is affected by body blocking, room geometry, radio interference, and device orientation. Treat the heatmap as approximate.
- ML quality depends on the supplied training data. The built-in training metadata labels the dataset as realistic synthetic data; model metrics should not be interpreted as evidence of real-room accuracy.
- ML recommendations are dry-run decision support and never issue hardware commands.

## Related documentation

- [`backend/README.md`](backend/README.md) — backend setup, gateway usage, API list, database, and tests
- [`frontend/README.md`](frontend/README.md) — frontend setup and checks
- [`NATIVE_BLUETOOTH.md`](NATIVE_BLUETOOTH.md) — Windows/macOS two-computer BLE deployment and calibration
- [`backend/BLUETOOTH_DEVICE_TEST.md`](backend/BLUETOOTH_DEVICE_TEST.md) — physical BLE scenario test plan
