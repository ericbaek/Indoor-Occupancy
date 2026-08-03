# Native Bluetooth signal heatmap

Everything runs directly on the host operating system:

| Computer | Native processes |
|---|---|
| Main computer / Left | Flask backend, Vite frontend, `left-anchor` scanner |
| Right laptop | `right-anchor` scanner |

The heatmap represents relative BLE signal intensity. It does not count
devices or people and does not calculate distance or coordinates.

## Windows setup — run once on both computers

```powershell
cd Indoor-Occupancy\backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

On the Main computer only:

```powershell
cd ..\frontend
npm install
```

## Windows Main computer — manual run

Open three PowerShell terminals.

Terminal 1 — Flask Backend:

```powershell
cd Indoor-Occupancy\backend
.\.venv\Scripts\python.exe .\run.py
```

Terminal 2 — Vite Frontend:

```powershell
cd Indoor-Occupancy\frontend
npm run dev -- --host 0.0.0.0
```

Terminal 3 — Left scanner:

```powershell
cd Indoor-Occupancy\backend
$env:ANCHOR_ID="left-anchor"
$env:BACKEND_URL="http://127.0.0.1:5000/api/bluetooth/signals"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

## Windows Main computer — one launcher

Instead of opening the three terminals manually, run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_main_windows.ps1
```

The launcher creates missing Python/npm dependencies and opens three visible
PowerShell windows so Backend, Frontend, and scanner logs remain available.

## Windows Right laptop

Replace the IP with the Main computer's Wi-Fi IPv4 address:

```powershell
cd Indoor-Occupancy
powershell -ExecutionPolicy Bypass -File .\run_right_anchor_windows.ps1 -MainIp 192.168.1.220
```

Manual equivalent:

```powershell
cd Indoor-Occupancy\backend
$env:ANCHOR_ID="right-anchor"
$env:BACKEND_URL="http://192.168.1.220:5000/api/bluetooth/signals"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

## macOS

Run once on both Macs:

```bash
cd Indoor-Occupancy/backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

On the Main Mac only:

```bash
cd ../frontend
npm install
```

Main Mac uses three Terminal tabs:

```bash
# Backend
cd Indoor-Occupancy/backend
.venv/bin/python run.py
```

```bash
# Frontend
cd Indoor-Occupancy/frontend
npm run dev -- --host 0.0.0.0
```

```bash
# Left scanner
cd Indoor-Occupancy/backend
export ANCHOR_ID=left-anchor
export BACKEND_URL=http://127.0.0.1:5000/api/bluetooth/signals
.venv/bin/python scripts/ble_scanner.py
```

Right Mac:

```bash
cd Indoor-Occupancy/backend
export ANCHOR_ID=right-anchor
export BACKEND_URL=http://<MAIN_IP>:5000/api/bluetooth/signals
.venv/bin/python scripts/ble_scanner.py
```

Allow Terminal Bluetooth access when macOS asks.

## Open the heatmap

Main computer:

```text
http://localhost:5173
```

Another computer:

```text
http://<MAIN_IP>:5173
```

The `Bluetooth Signal Intensity` card is below the CO2 chart on Dashboard.

Postman:

```http
GET http://<MAIN_IP>:5000/api/bluetooth/signal-strength
```

## Calibration

Set offsets in the Main computer's Backend terminal before `run.py`:

```powershell
$env:BLE_LEFT_RSSI_OFFSET="0"
$env:BLE_RIGHT_RSSI_OFFSET="4"
.\.venv\Scripts\python.exe .\run.py
```

Other configurable values are `BLE_MINIMUM_RSSI`, `BLE_MAXIMUM_RSSI`,
`BLE_EMA_ALPHA`, and `BLE_ANCHOR_TIMEOUT_SECONDS`.

## Troubleshooting

- `Failed to fetch`: confirm Flask is running on port 5000 before Vite starts.
- Right anchor cannot connect: allow inbound TCP port 5000 on the Main PC.
- Remote heatmap cannot open: allow inbound TCP port 5173 on the Main PC.
- One side is offline: its scanner has not posted within 15 seconds.
- The heatmap needs approximately 4-8 seconds for the first scan windows.
