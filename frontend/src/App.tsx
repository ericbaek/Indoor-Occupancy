import { Users, Wind, Activity, Clock3 } from "lucide-react";
import Sidebar from "./components/Sidebar";
import Topbar from "./components/Topbar";
import StatCard from "./components/StatCard";
import RadarScope from "./components/RadarScope";
import OccupancyChart from "./components/OccupancyChart";
import RoomList from "./components/RoomList";
import SensorTable from "./components/SensorTable";
import AlertsPanel from "./components/AlertsPanel";
import { radarTargets, sensorNodes, rooms, alerts, occupancySeries } from "./data";
import "./App.css";

function App() {
  const currentOccupancy = rooms.reduce((sum, r) => sum + r.occupancy, 0);
  const capacity = rooms.reduce((sum, r) => sum + r.capacity, 0);
  const avgCo2 = Math.round(sensorNodes.reduce((sum, n) => sum + n.co2, 0) / sensorNodes.length);
  const motionActive = sensorNodes.some((n) => n.pirOut || n.pirIn);
  const activeTargets = radarTargets.filter((t) => t.distance > 0).length;

  return (
    <div className="app-shell">
      <Sidebar />
      <main className="app-main">
        <Topbar />

        <section className="stat-grid">
          <StatCard
            icon={<Users size={17} strokeWidth={2} />}
            label="Current occupancy"
            value={String(currentOccupancy)}
            sub={`/ ${capacity} capacity`}
            tone="signal"
            tag="Fusion estimate"
          />
          <StatCard
            icon={<Wind size={17} strokeWidth={2} />}
            label="Avg CO\u2082 level"
            value={String(avgCo2)}
            unit="ppm"
            sub="Across 5 nodes"
            tone={avgCo2 > 900 ? "amber" : "blue"}
            tag={avgCo2 > 900 ? "Elevated" : "Healthy range"}
          />
          <StatCard
            icon={<Activity size={17} strokeWidth={2} />}
            label="Motion status"
            value={motionActive ? "Active" : "Idle"}
            sub="Dual PIR, doorway"
            tone={motionActive ? "amber" : "neutral"}
            tag={motionActive ? "PIR triggered" : "No motion"}
          />
          <StatCard
            icon={<Clock3 size={17} strokeWidth={2} />}
            label="Last updated"
            value="10:24:30"
            sub="10 Jul 2026"
            tone="blue"
            tag="Live"
          />
        </section>

        <section className="mid-grid">
          <OccupancyChart data={occupancySeries} capacity={40} />
          <RadarScope targets={radarTargets} />
        </section>

        <section className="lower-grid">
          <RoomList rooms={rooms} />
          <AlertsPanel alerts={alerts} />
        </section>

        <section style={{ marginBottom: 14 }}>
          <SensorTable nodes={sensorNodes} />
        </section>

        <p className="app-footer">
          {`Occupancy is estimated from anonymous sensor fusion \u2014 no cameras, no device IDs, ${activeTargets} live mmWave target${activeTargets === 1 ? "" : "s"} tracked.`}
        </p>
      </main>
    </div>
  );
}

export default App;
