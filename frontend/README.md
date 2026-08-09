# Indoor Occupancy Frontend

React and Vite dashboard for live occupancy, radar, CO₂, BLE heatmap, reports and ML predictions.

## Setup

```powershell
cd frontend
npm ci
```

## Run

```powershell
$env:VITE_API_BASE_URL = "http://127.0.0.1:5001/api"
npm run dev -- --host 0.0.0.0
```

Open `http://localhost:5173`.

On the Dashboard, `+` or `↑` adds one occupant and `-` or `↓` removes one occupant. The backend clamps occupancy at zero.

## Checks

```powershell
npm test
npm run lint
npm run build
```
