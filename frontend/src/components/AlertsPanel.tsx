import { AlertTriangle, WifiOff } from "lucide-react";
import type { Alert } from "../data";
import "./AlertsPanel.css";

const ICONS: Record<Alert["kind"], typeof AlertTriangle> = {
  capacity: AlertTriangle,
  offline: WifiOff,
};

export default function AlertsPanel({ alerts }: { alerts: Alert[] }) {
  return (
    <div className="alerts-card">
      <div className="room-head">
        <div className="chart-title">Recent alerts</div>
        <button className="link-btn">View all &rarr;</button>
      </div>
      <div className="alerts-rows">
        {alerts.map((a) => {
          const Icon = ICONS[a.kind];
          return (
            <div key={a.id} className="alert-row">
              <span className={`alert-icon alert-icon-${a.kind}`}>
                <Icon size={15} strokeWidth={2} />
              </span>
              <div className="alert-body">
                <div className="alert-title">{a.title}</div>
                <div className="alert-detail">{a.detail}</div>
              </div>
              <span className="alert-time">{a.time}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
