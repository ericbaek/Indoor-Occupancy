import { Moon, Sun } from "lucide-react";
import type { HealthState } from "../hooks/useHealthCheck";
import "./Topbar.css";

type TopbarProps = {
  title: string;
  sub: string;
  theme: "light" | "dark";
  onToggleTheme: () => void;
  health: HealthState;
};

function healthLabel(health: HealthState): string {
  if (health.status === "checking") return "Checking backend\u2026";
  if (health.status === "ok") return `Backend OK \u00b7 DB ${health.database ?? "unknown"}`;
  return "Backend unreachable";
}

export default function Topbar({ title, sub, theme, onToggleTheme, health }: TopbarProps) {
  const isLight = theme === "light";

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
        <button
          className="icon-btn"
          type="button"
          onClick={onToggleTheme}
          aria-label={isLight ? "Switch to dark mode" : "Switch to light mode"}
        >
          {isLight ? <Moon size={16} strokeWidth={2} /> : <Sun size={16} strokeWidth={2} />}
        </button>
      </div>
    </header>
  );
}