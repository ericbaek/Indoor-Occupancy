# Real Bluetooth Computer/Device Test (3 to 5 devices)

This mode counts actual participating Bluetooth advertisers, not mock rows.
Two fixed scanners compare rolling RSSI and place each unique device in the
Left or Right heatmap. The backend displays at most five active devices.

## Three-computer layout

| Computer | Physical side | Processes |
|---|---|---|
| Main PC | Left | Backend, frontend, LEFT advertiser, `anchor-left` scanner |
| Laptop 2 | Right | RIGHT-1 advertiser, `anchor-right` scanner |
| Laptop 3 | Right | RIGHT-2 advertiser, browser/Postman |

All computers must use the same Wi-Fi network, have Bluetooth enabled, and use
the `feature/ble-tracking` branch. Replace `<MAIN_PC_IP>` below with the Main
PC's Wi-Fi IPv4 address from `ipconfig`.

Run this once in `backend` on each computer:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## 1. Main PC (Left)

Backend terminal:

```powershell
cd backend
$env:FLASK_HOST="0.0.0.0"
.\.venv\Scripts\python.exe .\run.py
```

Advertiser terminal (start this before the scanner):

```powershell
cd backend
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py `
  --device-id LEFT `
  --co-located-anchor anchor-left `
  --backend-url http://127.0.0.1:5000/api/bluetooth/readings
```

Continue only after it prints `Bluetooth publisher: started`.

Left scanner terminal:

```powershell
cd backend
$env:SCANNER_ID="anchor-left"
$env:BACKEND_URL="http://127.0.0.1:5000/api/bluetooth/readings"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

Frontend terminal:

```powershell
cd frontend
$env:VITE_API_BASE_URL="http://<MAIN_PC_IP>:5000/api"
npm install
npm run dev -- --host 0.0.0.0
```

## 2. Laptop 2 (Right anchor PC)

Advertiser terminal (start this before the scanner):

```powershell
cd backend
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py `
  --device-id RIGHT-1 `
  --co-located-anchor anchor-right `
  --backend-url http://<MAIN_PC_IP>:5000/api/bluetooth/readings
```

Right scanner terminal:

```powershell
cd backend
$env:SCANNER_ID="anchor-right"
$env:BACKEND_URL="http://<MAIN_PC_IP>:5000/api/bluetooth/readings"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

## 3. Laptop 3 (Right tracked PC)

Advertiser terminal:

```powershell
cd backend
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py --device-id RIGHT-2
```

Laptop 3 is not another anchor, so do not set `--co-located-anchor`.

Open the heatmap:

```text
http://<MAIN_PC_IP>:5173
```

## Expected result

```http
GET http://<MAIN_PC_IP>:5000/api/bluetooth/count
```

```json
{
  "total_active_devices": 3,
  "max_devices": 5,
  "zones": {
    "left": { "count": 1 },
    "right": { "count": 2 }
  },
  "unassigned_count": 0,
  "ignored_active_devices": 0
}
```

Detailed device/RSSI data:

```http
GET http://<MAIN_PC_IP>:5000/api/bluetooth/devices
```

## Adding computers 4 and 5

Run the advertiser on each additional computer with a unique ID:

```powershell
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py --device-id PC-04
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py --device-id PC-05
```

The two anchors will detect them and the backend will count them up to the
configured maximum of five.

## Discovering and allowlisting a non-project BLE device

Discovery mode prints nearby BLE advertisers and sends no data:

```powershell
$env:BLE_DISCOVERY="1"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

After noting a stable address or exact advertised name, restart both anchors
with the same comma-separated allowlist:

```powershell
Remove-Item Env:BLE_DISCOVERY -ErrorAction SilentlyContinue
$env:BLE_TARGETS="AA:BB:CC:DD:EE:01,Exact Device Name"
```

Avoid `BLE_SCAN_ALL=1` outside a controlled room. Nearby watches and earbuds,
and devices that rotate private Bluetooth addresses, can otherwise create an
incorrect count.

## Troubleshooting

- `radio not available`: turn Bluetooth on and confirm the PC has BLE support.
- `Bluetooth advertising resource in use`: close other beacon/advertising
  applications, then start the advertiser before the scanner.
- `not supported by this Bluetooth adapter`: use a BLE-capable USB adapter or
  attach a Nano/beacon to that computer.
- `unassigned_count > 0`: the device has not yet been heard by both anchors.
- A device disappears after 5 seconds without a reading by design.

Windows provides BLE advertisement publishing on a best-effort basis; support
depends on the PC's Bluetooth adapter and driver. The advertiser exits instead
of generating a false presence record when publishing fails.
