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
import Reports from "./pages/Reports";
import Settings from "./pages/Settings";
// Rooms and alerts have no backend support yet (the real system is a
// single doorway, not multi-room) — these stay mock until that data model
// exists on the backend. Sensors is real (see SensorTable / data.radarDevices
// / data.co2Ppm below).
import { rooms, alerts } from "./data";
import { useOccupancyData } from "./hooks/useOccupancyData";
import { useHealthCheck } from "./hooks/useHealthCheck";
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

// Maps the backend's co2_level classification to a StatCard tone + tag.
// Values match _co2_level() in backend/app/routes.py: "normal" (<800ppm),
// "elevated" (800-1500ppm), "high" (>1500ppm). Falls back gracefully if
// the backend sends something unrecognised (or none yet).
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
                sub={`Polling every ${preferences.pollMs < 1000 ? `${preferences.pollMs}ms` : `${preferences.pollMs / 1000}s`}`}
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
