# Room Sense — Indoor Occupancy Monitoring

A team-built IoT prototype that combines doorway sensing, environmental monitoring, and a web dashboard to help an operator understand room occupancy and sensor reliability.

**Stack:** React · TypeScript · Flask · SQLite · MicroPython/Arduino · Bleak · scikit-learn · Docker Compose

Eric Baek coordinated development across the non-frontend parts of the project and contributed hands-on to backend services, sensor/firmware development, and system integration. His work also included Docker/Compose setup and project documentation. Frontend implementation was handled by other team members; the complete system was a collaborative team effort.

[Watch the 29-second doorway walkthrough](IMG_1965.MOV)

## What it does

- Tracks entry/exit events and maintains an occupancy total with duplicate-event protection and manual calibration.
- Displays mmWave targets, CO₂, temperature, humidity, sensor health, and occupancy history in a React dashboard.
- Compares the event-based occupancy estimate with radar presence and flags disagreement for operator review.
- Combines two BLE anchors into a relative left/right signal-strength view.
- Provides report summaries and CSV/PDF exports, plus an optional occupancy forecasting pipeline.

This repository contains the implementation and automated tests. It does not include a hosted demo, trained model bundle, training dataset, or measured real-room accuracy results. The **Rooms** and **Alerts** views use demonstration data; the main dashboard and reports query the backend.

## Demo videos

Recorded prototype demonstrations (original MOV files; open the link to view or download):

| Video | What it shows | Duration |
| --- | --- | --- |
| [Dashboard overview](IMG_1127.mov) | Dashboard view with the occupancy forecast panel and BLE status. | 21 sec |
| [Doorway walkthrough](IMG_1965.MOV) | A person approaching the instrumented doorway, with the dashboard visible alongside the setup. | 29 sec |
| [Sensor setup close-up](IMG_1966.MOV) | Close-up of the doorway-mounted sensor hardware and wiring. | 44 sec |

These recordings illustrate the prototype; they are not an accuracy benchmark. Playback depends on browser and codec support; download the file if needed.

## How it works

```text
RD03D mmWave + PIR ──┐
SCD41 environment ──┴─ USB serial → Python gateway ─┐
Two BLE anchor computers ──────── Bleak scanners ───┤
                                                  ▼
                                            Flask REST API
                                                  │
                                                SQLite
                                                  │
                                   ┌──────────────┴──────────────┐
                                   ▼                             ▼
                            React dashboard             Optional ML scheduler
```

The current [doorway firmware](sensor/PIR_and_mmWave.py) uses **mmWave target crossings as the primary entry/exit signal**. It matches detections between frames, confirms which side of the doorway a target occupies, and adds recent PIR activity as supporting confidence information. The backend retains legacy PIR naming in parts of its API and ML feature schema.

The [serial gateway](backend/scripts/hardware_gateway.py) routes newline-delimited JSON by `message_type`: `occupancy_event`, `radar`, or `environment`. Flask validates and stores readings, while the frontend polls the API. Radar snapshots support up to three targets. BLE scanners report aggregate RSSI summaries rather than device counts or precise locations.

## Project context and contributions

Developed as a **COMP6733 team project**. The sensing, backend, dashboard, and forecasting components reflect work by multiple contributors.

Other contributor names recorded in Git history include Aarya Mane, Chanhee Lee, Francesco Cliff Hervenlee, Shreyas / Shreyas Sinha, `kheliff`, and `Backend Dev`. Commit authorship is an incomplete record of individual roles.

## Run locally without hardware

Use Python 3.12 and Node.js 22.12+ (matching the container runtime families). Run commands from the repository root unless a `cd` is shown.

### 1. Start the backend

macOS/Linux:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
FLASK_HOST=127.0.0.1 FLASK_DEBUG=false ML_LIVE_PREDICTION_ENABLED=false \
  python run.py --no-keyboard-controls
```

Windows PowerShell:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:FLASK_HOST = "127.0.0.1"
$env:FLASK_DEBUG = "false"
$env:ML_LIVE_PREDICTION_ENABLED = "false"
.\.venv\Scripts\python.exe run.py --no-keyboard-controls
```

The backend creates `backend/instance/occupancy.db` when started from `backend/`. Check it with `curl http://localhost:5000/api/health`. Port 5000 must be available; `FLASK_PORT` can override it, but update the frontend and sender URLs accordingly.

### 2. Start the dashboard

In another terminal:

```bash
cd frontend
npm ci
```

macOS/Linux:

```bash
VITE_API_BASE_URL=http://localhost:5000/api npm run dev
```

Windows PowerShell:

```powershell
$env:VITE_API_BASE_URL = "http://localhost:5000/api"
npm run dev
```

Open [localhost:5173](http://localhost:5173).

### 3. Add sample data

With the backend running, use another terminal with the backend virtual environment activated:

```bash
cd backend
python scripts/send_pir_test_events.py
python scripts/send_environment_test_data.py --url http://localhost:5000
python scripts/seed_reports_demo_data.py --db instance/occupancy.db --days 7 --seed 42
```

On a fresh database, the occupancy sender posts four entries and two exits, yielding **2 occupants**. Repeating it returns duplicate-event responses instead of counting the same events again. The report seeder adds generated history and demonstration headcounts; its evaluation metrics are **not field-validation results**. These commands write sample data, so use a separate local database from any real deployment.

The environment sender also includes invalid-payload validation cases. For radar payload examples, run `python scripts/send_radar_test_data.py`. It includes deliberately invalid requests to exercise validation, so some printed error markers are expected.

### Docker alternative

Before running Compose, change the frontend service's `VITE_API_BASE_URL` in [compose.yaml](compose.yaml) to `http://localhost:5001/api`. The checked-in value points to a development LAN address. For a local browser, only `http://localhost:5173` is needed in `CORS_ORIGINS`.

```bash
docker compose up --build
```

Open [localhost:5173](http://localhost:5173); backend health is at `http://localhost:5001/api/health`. SQLite data persists in the `backend-data` volume. Compose starts development servers and does not start physical sensor gateways or BLE scanners.

## Connect hardware

The repository includes RD03D/PIR MicroPython firmware, SCD41 sensor code, and an Arduino BLE tag sketch. Wiring, board libraries, serial ports, and doorway thresholds must match your hardware.

With the backend running and its virtual environment active:

```bash
python backend/scripts/hardware_gateway.py \
  --mode serial --port /dev/ttyACM0 --baudrate 115200 \
  --url http://localhost:5000
```

Replace the port for your host (for example, `COM5` on Windows). See [backend setup and API notes](backend/README.md) and the [two-computer Bluetooth guide](NATIVE_BLUETOOTH.md) for scanner setup, permissions, and calibration. The [BLE scenario document](backend/BLUETOOTH_DEVICE_TEST.md) is a test plan, not recorded test results.

The Windows `run_main_windows.ps1` launcher starts the backend, frontend, and left BLE scanner; `run_right_anchor_windows.ps1` starts the second anchor. **`run_demo_windows.ps1` deletes the local database before starting**; review its `-WhatIf` output before using it.

## Optional forecasting

The [ML pipeline](backend/ml/train.py) aggregates five-minute sensor windows and predicts occupancy 30 minutes ahead. It also exposes overcrowding risk, empty-room probabilities, and ventilation recommendations. Recommendations are **dry-run only** and do not control ventilation hardware.

A fresh checkout has no model. To train one, supply a compatible `.xlsx` or `.csv` dataset with the columns validated in [data_loader.py](backend/ml/data_loader.py) and [config.py](backend/ml/config.py):

```bash
cd backend
python -m ml.train --dataset /path/to/dataset.xlsx \
  --output-dir models/predictive_occupancy --room-capacity 30
```

Training compares candidate models and baselines using chronological splits and leakage/safety checks. Its configuration labels the data `realistic_synthetic` and uses fixed July–August 2026 splits in Australia/Sydney time. A new dataset may require adapting that configuration. No accuracy claim is made here because neither evaluation artifacts nor the dataset are tracked in the current tree.

For live predictions, enable `ML_LIVE_PREDICTION_ENABLED=true` and set `ML_BLE_LEFT_SCANNER_ID=left-anchor` and `ML_BLE_RIGHT_SCANNER_ID=right-anchor` to match the scanner IDs. The ML defaults (`anchor-left` / `anchor-right`) differ from BLE ingestion defaults.

## Checks

Backend (with its virtual environment activated):

```bash
cd backend
ML_LIVE_PREDICTION_ENABLED=false python -m pytest -q
```

In PowerShell, set `$env:ML_LIVE_PREDICTION_ENABLED = "false"` before the pytest command.

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

Tests cover ingestion and validation, occupancy state/calibration, BLE and serial routing, ML feature/split/leakage/safety behavior, and selected dashboard components and hooks. Passing software tests does not establish physical counting accuracy.

## Limitations

- Single-doorway prototype: missed crossings can cause count drift, requiring calibration. Radar tracks are not guaranteed unique people over time.
- CO₂ is a delayed contextual signal. BLE RSSI varies with obstructions and orientation; it indicates relative signal strength, not distance or a people count.
- No tracked real-world benchmark or trained-model results support a quantitative performance claim.
- Flask development serving, unauthenticated write/reset endpoints, and a development secret default make this a trusted-local-network prototype. Add authentication, production serving, and deployment configuration before hosting it publicly.
- Python dependencies are unpinned, so installation is not an exact environment reproduction.

## Repository guide

| Path | Contents |
| --- | --- |
| [backend/](backend/) | Flask API, SQLite storage, ML pipeline, gateway/scanner scripts, tests |
| [frontend/](frontend/) | React dashboard, reports/settings, polling hooks, component tests |
| [sensor/](sensor/) | Doorway and environment firmware, RD03D driver |
| [hardware/](hardware/) | Arduino BLE tag sketch |
| [NATIVE_BLUETOOTH.md](NATIVE_BLUETOOTH.md) | Two-anchor deployment and calibration |
