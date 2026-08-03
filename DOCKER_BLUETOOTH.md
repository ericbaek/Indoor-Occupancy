# Windows and macOS Docker + Bluetooth setup

The Flask API and React heatmap run in Docker on the **Main computer**. BLE
scanning and advertising run natively on each computer because Docker Desktop
does not directly expose the host Bluetooth radio to ordinary Linux
containers.

## Architecture

| Machine | Docker | Native Bluetooth processes |
|---|---|---|
| Main computer / Left | Backend + frontend | `anchor-left` scanner; optional advertiser |
| Right laptop | No Docker required | `anchor-right` scanner; optional advertiser |
| Additional tracked laptops | No Docker required | advertiser only |

All computers must be on the same Wi-Fi network. Allow inbound TCP port 5000
on the Main computer so the remote scanner can post readings. Port 8080 is the
heatmap UI.

## 1. Run Docker on the Main computer (Windows or macOS)

Install and start Docker Desktop, then run these commands from the repository
root:

```text
docker compose up --build -d
docker compose ps
```

Open:

```text
Heatmap: http://localhost:8080
API:     http://localhost:5000/api/health
Count:   http://localhost:5000/api/bluetooth/count
Devices: http://localhost:5000/api/bluetooth/devices
```

From another laptop, replace `localhost` with the Main computer's Wi-Fi IPv4
address, for example `http://192.168.1.220:8080`.

Useful Docker commands:

```text
docker compose logs -f
docker compose restart
docker compose down
```

`docker compose down` preserves the named SQLite volume. Do not add `-v` if
you want to keep recorded sensor data.

## 2. Install the native BLE helper on Windows

In PowerShell, from the repository root:

```powershell
cd backend
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Left scanner on the Main Windows computer:

```powershell
$env:SCANNER_ID="anchor-left"
$env:BACKEND_URL="http://127.0.0.1:5000/api/bluetooth/readings"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

Right scanner on a Windows laptop:

```powershell
$env:SCANNER_ID="anchor-right"
$env:BACKEND_URL="http://<MAIN_IP>:5000/api/bluetooth/readings"
.\.venv\Scripts\python.exe .\scripts\ble_scanner.py
```

Advertise a Windows computer as a tracked device:

```powershell
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py --device-id PC1
```

If that computer is also the Right anchor, run this instead:

```powershell
.\.venv\Scripts\python.exe .\scripts\ble_advertiser_windows.py `
  --device-id RIGHT1 `
  --co-located-anchor anchor-right `
  --backend-url http://<MAIN_IP>:5000/api/bluetooth/readings
```

## 3. Install the native BLE helper on macOS

In Terminal, from the repository root:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

The first scan may show a macOS Bluetooth permission prompt. Select **Allow**.
If it was denied, enable Terminal under **System Settings > Privacy & Security
> Bluetooth**.

Left scanner on a Main Mac:

```bash
export SCANNER_ID=anchor-left
export BACKEND_URL=http://127.0.0.1:5000/api/bluetooth/readings
python scripts/ble_scanner.py
```

Right scanner on a Mac laptop:

```bash
export SCANNER_ID=anchor-right
export BACKEND_URL=http://<MAIN_IP>:5000/api/bluetooth/readings
python scripts/ble_scanner.py
```

Advertise a Mac as a tracked device. `swift` is included with Xcode Command
Line Tools; run `xcode-select --install` once if the command is missing.

```bash
swift scripts/ble_advertiser_macos.swift --device-id MAC1
```

If that Mac is also the Right anchor:

```bash
swift scripts/ble_advertiser_macos.swift \
  --device-id RIGHT1 \
  --co-located-anchor anchor-right \
  --backend-url http://<MAIN_IP>:5000/api/bluetooth/readings
```

Keep the advertiser and scanner open in separate Terminal windows. Apple
advertises the Mac as `ROOM-TAG-<ID>`; both anchors report that same ID.

## 4. Mixed Windows/macOS test

1. Start Docker on the Main computer.
2. Start `anchor-left` natively on the Main computer.
3. Start `anchor-right` natively on the Right laptop.
4. Start one advertiser on each computer/device that should be counted. Give
   every advertiser a unique ID.
5. Open `http://<MAIN_IP>:8080` and wait about 2 seconds for RSSI smoothing.
6. Verify `GET http://<MAIN_IP>:5000/api/bluetooth/devices` in Postman.

The same physical device is counted once. It changes side only when the other
anchor's smoothed RSSI is at least 5 dBm stronger. A device disappears from the
active count after the configured BLE timeout when neither anchor detects it.

## Troubleshooting

- API works but the UI says Offline: open `http://<MAIN_IP>:8080`, not the old
  Vite port 5173, and check `docker compose ps`.
- Remote scanner cannot post: allow inbound TCP 5000 in the Main computer's
  firewall and verify both computers are on the same Wi-Fi network.
- macOS scanner shows no devices: turn Bluetooth on and check Terminal's
  Bluetooth privacy permission.
- macOS advertiser fails: keep Terminal in the foreground, use an ID of at most
  8 characters, and close other BLE advertising applications.
- One device is `unassigned`: both anchors must hear it before Left/Right can
  be compared.
