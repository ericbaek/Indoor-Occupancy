import { Users, Radar, ShieldCheck, ShieldAlert, Clock3 } from "lucide-react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import StatCard from "./components/StatCard";
import RadarScope from "./components/RadarScope";
import OccupancyChart from "./components/OccupancyChart";
import RoomList from "./components/RoomList";
import SensorTable from "./components/SensorTable";
import AlertsPanel from "./components/AlertsPanel";
// Rooms, sensor nodes (CO2/battery), and alerts have no backend support yet
// (the real system is a single doorway, not multi-room) — these stay mock
// until that data model exists on the backend.
import { sensorNodes, rooms, alerts } from "./data";
import { useOccupancyData } from "./hooks/useOccupancyData";
import "./App.css";

function App() {
  const data = useOccupancyData();

  const activeTargets = data.radarTargets.length;
  const lastUpdatedLabel = data.lastUpdated.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />

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
          <StatCard
            icon={data.status === "confirmed" ? <ShieldCheck size={17} strokeWidth={2} /> : <ShieldAlert size={17} strokeWidth={2} />}
            label="Detection status"
            value={data.status === "confirmed" ? "Confirmed" : data.status === "uncertain" ? "Uncertain" : "—"}
            sub="PIR + radar agreement"
            tone={data.status === "confirmed" ? "blue" : "amber"}
            tag={data.status === "uncertain" ? "Mismatch" : "In sync"}
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
            icon={<Clock3 size={17} strokeWidth={2} />}
            label="Last updated"
            value={lastUpdatedLabel}
            sub="Polling every 3s"
            tone="blue"
            tag={data.isLive ? "Live" : "Stale"}
          />
        </section>

        <section className="mid-grid">
          <OccupancyChart data={data.occupancySeries} capacity={40} />
          <RadarScope targets={data.radarTargets} />
        </section>

        {/* Rooms and alerts below are mock — no multi-room or alerting
            support in the backend yet. */}
        <section className="lower-grid">
          <RoomList rooms={rooms} />
          <AlertsPanel alerts={alerts} />
        </section>

        <section style={{ marginBottom: 14 }}>
          <SensorTable nodes={sensorNodes} />
        </section>

        <p className="app-footer">
          {`Occupancy is estimated from real PIR + mmWave sensor fusion \u2014 ${activeTargets} live radar target${activeTargets === 1 ? "" : "s"} tracked.`}
        </p>
      </main>
    </div>
  );
}

export default App;