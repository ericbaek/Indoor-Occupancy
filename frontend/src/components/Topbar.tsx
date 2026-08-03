import type { HealthState } from "../hooks/useHealthCheck";
import "./Topbar.css";

type TopbarProps = {
  title: string;
  sub: string;
  health: HealthState;
};

function healthLabel(health: HealthState): string {
  if (health.status === "checking") return "Checking backend\u2026";
  if (health.status === "ok") return `Backend OK \u00b7 DB ${health.database ?? "unknown"}`;
  return "Backend unreachable";
}

export default function Topbar({ title, sub, health }: TopbarProps) {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-sub">{sub}</p>
      </div>
      <div className="topbar-actions">
        <span
          className={`health-badge ${health.status === "ok" ? "active" : health.status === "error" ? "down" : "inactive"}`}
          title={healthLabel(health)}
        >
          <span className="health-dot" />
          {health.status === "ok" ? "Online" : health.status === "error" ? "Offline" : "\u2026"}
        </span>
      </div>
    </header>
  );
}
