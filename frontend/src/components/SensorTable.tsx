import type { SensorNode } from "../data";
import "./SensorTable.css";

export default function SensorTable({ nodes }: { nodes: SensorNode[] }) {
  return (
    <div className="sensor-card">
      <div className="chart-title">Sensor node status</div>
      <div className="chart-sub" style={{ marginBottom: 14 }}>
        PIR-IN / PIR-OUT &middot; mmWave targets (RD-03D)
      </div>

      <div className="sensor-table">
        <div className="sensor-row sensor-row-head">
          <span>Node</span>
          <span>Room</span>
          <span>PIR in</span>
          <span>PIR out</span>
          <span>mmWave</span>
          <span>Status</span>
        </div>
        {nodes.map((n) => (
          <div key={n.id} className="sensor-row">
            <span className="sensor-id">{n.id}</span>
            <span>{n.room}</span>
            <span className={n.pirIn ? "sensor-yes" : "sensor-no"}>{n.pirIn ? "Yes" : "No"}</span>
            <span className={n.pirOut ? "sensor-yes" : "sensor-no"}>{n.pirOut ? "Yes" : "No"}</span>
            <span className="sensor-mono">{n.mmwaveTargets}</span>
            <span className={`sensor-status sensor-status-${n.status}`}>
              <span className="sensor-status-dot" />
              {n.status === "online" ? "Online" : "Offline"}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
