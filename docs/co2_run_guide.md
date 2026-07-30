# CO₂ Pipeline — Quick-Start Guide

This guide covers the SCD41 CO₂ sensor pipeline only.  
It assumes the rest of the project (PIR, mmWave, frontend) is set up separately.

---

## Hardware

| Component | Detail |
|---|---|
| Board | Arduino Nano 33 BLE Sense Rev2 |
| Sensor | DFRobot Gravity SCD41 (SEN0536) |
| I²C address | `0x62` |
| SDA | A4 |
| SCL | A5 |
| Power | 3.3 V |

---

## A — Nano Setup (Thonny)

> [!IMPORTANT]
> Close Thonny **before** launching the gateway (step C). Only one program can
> use the serial port at a time.

1. Open **Thonny** (`Tools → Options → Interpreter`).  
   Select **MicroPython (Arduino Nano 33 BLE Sense)** and the correct COM port.

2. Open `sensor/co2.py` from this repository.

3. Click **Run (F5)** to run interactively.  
   You should see one JSON line every ~5 seconds:
   ```
   {"message_type":"environment","device_id":"scd41-nano-01","uptime_ms":12000,"co2_ppm":491,"temperature_c":23.6,"humidity_percent":37.9}
   ```

4. Once you confirm the output looks correct, save the file **to the Nano** as
   `main.py` (File → Save copy… → MicroPython device → `main.py`).  
   This makes it start automatically every time the Nano powers up.

5. **Close Thonny** now.

---

## B — Backend

Open a terminal in the `backend/` directory and run:

```bash
python run.py
```

Expected output:
```
  Backend : http://localhost:5000
  Database: instance/occupancy.db
  Debug   : True
```

Leave this terminal open.

---

## C — Real Hardware Gateway

Open a **second terminal** in the `backend/` directory and run:

```bash
python scripts/hardware_gateway.py --mode serial --port COM_PORT --baudrate 115200
```

Replace `COM_PORT` with the actual Windows port number, for example:

```bash
python scripts/hardware_gateway.py --mode serial --port COM5 --baudrate 115200
```

> [!TIP]
> To find the correct COM port: open **Device Manager → Ports (COM & LPT)**
> and look for "USB Serial Device" while the Nano is connected.

Expected gateway output on each successful reading:
```
15:32:01 [INFO] POST /api/co2/readings → 201 {"success": true, ...}
```

---

## D — Verification

With the backend and gateway both running, verify the latest reading:

```bash
curl http://localhost:5000/api/co2/latest/scd41-nano-01
```

Expected response (HTTP 200):
```json
{
  "device_id": "scd41-nano-01",
  "uptime_ms": 12000,
  "co2_ppm": 491,
  "temperature_c": 23.6,
  "humidity_percent": 37.9,
  "received_at": "2026-07-30T05:32:01.123456+00:00"
}
```

Additional endpoints:

```bash
# All devices (returns {"devices": [...]})
curl http://localhost:5000/api/co2/latest

# Last 50 readings for the Nano
curl http://localhost:5000/api/co2/history/scd41-nano-01

# Unified occupancy + CO2 status (used by the frontend)
curl http://localhost:5000/api/occupancy/status
```

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `Cannot open serial port` | Thonny still open, or wrong COM port | Close Thonny; check Device Manager |
| Gateway connects but no POSTs | Nano not running `main.py` / no CO₂ sensor | Verify JSON in Thonny first |
| `404` on `/api/co2/latest/scd41-nano-01` | No reading received yet | Wait ≥10 s after gateway starts |
| `400` from backend | Malformed JSON from sensor | Check Thonny output; ensure `co2.py` is saved correctly |
| CRC errors in Thonny | Loose I²C wiring | Check SDA/SCL connections on A4/A5 |
