import { BatteryMedium } from "lucide-react";
import type { SensorNode } from "../data";
import "./SensorTable.css";

export default function SensorTable({ nodes }: { nodes: SensorNode[] }) {
  return (
    <div className="sensor-card">
      <div className="chart-title">Sensor node status</div>
      <div className="chart-sub" style={{ marginBottom: 14 }}>
        CO&#8322; (SCD41) &middot; PIR-OUT / PIR-IN &middot; mmWave targets (RD-03D)
      </div>

      <div className="sensor-table">
        <div className="sensor-row sensor-row-head">
          <span>Node</span>
          <span>Room</span>
          <span>CO&#8322; ppm</span>
          <span>PIR out</span>
          <span>PIR in</span>
          <span>mmWave</span>
          <span>Status</span>
          <span>Battery</span>
        </div>
        {nodes.map((n) => (
          <div key={n.id} className="sensor-row">
            <span className="sensor-id">{n.id}</span>
            <span>{n.room}</span>
            <span className={n.co2 > 1000 ? "sensor-co2-hot" : n.co2 > 800 ? "sensor-co2-warm" : ""}>{n.co2}</span>
            <span className={n.pirOut ? "sensor-yes" : "sensor-no"}>{n.pirOut ? "Yes" : "No"}</span>
            <span className={n.pirIn ? "sensor-yes" : "sensor-no"}>{n.pirIn ? "Yes" : "No"}</span>
            <span className="sensor-mono">{n.mmwaveTargets}</span>
            <span className={`sensor-status sensor-status-${n.status}`}>
              <span className="sensor-status-dot" />
              {n.status === "online" ? "Online" : "Offline"}
            </span>
            <span className="sensor-battery">
              {n.battery != null ? (
                <>
                  <BatteryMedium size={14} strokeWidth={2} /> {n.battery}%
                </>
              ) : (
                <span className="sensor-no">&mdash;</span>
              )}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
