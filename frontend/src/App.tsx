import { useState } from "react";
import { Users, Radar, Clock3, Wind } from "lucide-react";
import Sidebar, { type NavItem } from "./components/Sidebar";
import Topbar from "./components/Topbar";
import StatCard from "./components/StatCard";
import DetectionStatusCard from "./components/DetectionStatusCard";
import RadarScope from "./components/RadarScope";
import OccupancyChart from "./components/OccupancyChart";
import Co2Chart from "./components/Co2Chart";
import RoomList from "./components/RoomList";
import SensorTable from "./components/SensorTable";
import AlertsPanel from "./components/AlertsPanel";
import BleTracker from "./components/BleTracker";
import PredictiveOccupancy from "./components/PredictiveOccupancy";
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
// Rooms and alerts use mock data; sensor values come from the backend.
import { rooms, alerts } from "./data";
import { useOccupancyData } from "./hooks/useOccupancyData";
import { useHealthCheck } from "./hooks/useHealthCheck";
import { useMlPrediction } from "./hooks/useMlPrediction";
import { usePreferences, formatTemperature } from "./hooks/usePreferences";
import "./App.css";

const TOPBAR_COPY: Record<NavItem, { title: string; sub: string }> = {
  Dashboard: { title: "Dashboard", sub: "Real-time occupancy across CSE teaching spaces" },
  Rooms: { title: "Rooms", sub: "Occupancy and capacity by teaching space (mock \u2014 backend is single-doorway)" },
  Sensors: { title: "Sensors", sub: "Live node status \u2014 online/offline from real backend readings" },
  Alerts: { title: "Alerts", sub: "Capacity and sensor connectivity events (mock)" },
  Reports: { title: "Reports", sub: "Historical exports and evaluation summaries" },
  Settings: { title: "Settings", sub: "Theme, units, refresh rate and CO2 chart threshold" },
};

// Matches the backend CO2 thresholds.
function co2Presentation(level: string | null): { tone: "signal" | "amber" | "red" | "neutral"; tag: string } {
  switch (level) {
    case "normal":
      return { tone: "signal", tag: "Good" };
    case "elevated":
      return { tone: "amber", tag: "Elevated" };
    case "high":
      return { tone: "red", tag: "High CO2" };
    default:
      return { tone: "neutral", tag: "No data" };
  }
}

function App() {
  const [page, setPage] = useState<NavItem>("Dashboard");
  const { preferences, update: updatePreference } = usePreferences();
  const data = useOccupancyData(preferences.pollMs);
  const mlPrediction = useMlPrediction(preferences.pollMs);
  const health = useHealthCheck();

  const activeTargets = data.radarTargets.length;
  const lastUpdatedLabel = data.lastUpdated.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  const co2 = co2Presentation(data.co2Level);

  return (
    <div className="app-shell">
      <Sidebar active={page} onNavigate={setPage} />
      <main className="app-main">
        <Topbar
          title={TOPBAR_COPY[page].title}
          sub={TOPBAR_COPY[page].sub}
          health={health}
        />

        {page === "Dashboard" && (
          <div className="dashboard-page">
            {data.error && (
              <p style={{ color: "#f87171", fontSize: 13, marginTop: 8 }}>
                Live data unavailable ({data.error}) — showing last known values.
              </p>
            )}

            <section className="stat-grid">
              <StatCard
                icon={<Users size={17} strokeWidth={2} />}
                label="Current occupancy"
                value={String(data.occupancy)}
                sub="PIR entry/exit count"
                tone="signal"
                tag={data.isLive ? "Live" : "Offline"}
              />
              <DetectionStatusCard
                status={data.status}
                occupancy={data.occupancy}
                radarPresence={data.radarPresence}
                radarTargetCount={data.radarTargetCount}
                mismatchStartedAt={data.mismatchStartedAt}
              />
              <StatCard
                icon={<Radar size={17} strokeWidth={2} />}
                label="Radar presence"
                value={data.radarPresence ? "Detected" : "None"}
                sub={`${data.radarTargetCount} target${data.radarTargetCount === 1 ? "" : "s"} (mmWave)`}
                tone={data.radarPresence ? "amber" : "neutral"}
                tag={data.radarPresence ? "Radar active" : "Clear"}
              />
              <StatCard
                icon={<Wind size={17} strokeWidth={2} />}
                label="CO2 level"
                value={data.co2Ppm !== null ? String(data.co2Ppm) : "—"}
                unit={data.co2Ppm !== null ? "ppm" : undefined}
                sub={data.temperatureC !== null ? `${formatTemperature(data.temperatureC, preferences.units)} \u00b7 ${data.humidityPercent}% humidity` : "SCD41 sensor"}
                tone={co2.tone}
                tag={co2.tag}
              />
              <StatCard
                icon={<Clock3 size={17} strokeWidth={2} />}
                label="Last updated"
                value={lastUpdatedLabel}
                sub={`Polling every ${preferences.pollMs / 1000}s`}
                tone="blue"
                tag={data.isLive ? "Live" : "Stale"}
              />
            </section>

            <section className="mid-grid">
              <OccupancyChart dataByRange={data.occupancySeriesByRange} capacity={40} />
              <RadarScope targets={data.radarTargets} />
            </section>

            <section className="co2-row">
              <Co2Chart data={data.co2History} deviceId={data.co2DeviceId} elevatedPpm={preferences.co2AlertThreshold} />
            </section>

            <PredictiveOccupancy
              prediction={mlPrediction.data}
              loading={mlPrediction.loading}
              error={mlPrediction.error}
            />

            <BleTracker signal={data.bleSignal} />

            <p className="app-footer">
              {`Occupancy is estimated from real PIR + mmWave sensor fusion \u2014 ${activeTargets} live radar target${activeTargets === 1 ? "" : "s"} tracked.`}
            </p>
          </div>
        )}

        {page === "Rooms" && (
          <section style={{ maxWidth: 640 }}>
            <RoomList rooms={rooms} />
          </section>
        )}

        {page === "Sensors" && (
          <section>
            <SensorTable
              radarDevices={data.radarDevices}
              co2Ppm={data.co2Ppm}
              co2DeviceId={data.co2DeviceId}
              lastEnvironmentUpdateAt={data.lastEnvironmentUpdateAt}
              lastOccupancyEventAt={data.lastOccupancyEventAt}
              lastEventType={data.events[0]?.event ?? null}
              bleSignal={data.bleSignal}
            />
          </section>
        )}

        {page === "Alerts" && (
          <section style={{ maxWidth: 640 }}>
            <AlertsPanel alerts={alerts} />
          </section>
        )}

        {page === "Reports" && <Reports />}

        {page === "Settings" && (
          <Settings preferences={preferences} onUpdate={updatePreference} />
        )}
      </main>
    </div>
  );
}

export default App;