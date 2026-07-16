import type { ReactNode } from "react";
import "./StatCard.css";

type Tone = "signal" | "amber" | "red" | "blue" | "neutral";

export default function StatCard({
  icon,
  label,
  value,
  unit,
  sub,
  tone,
  tag,
}: {
  icon: ReactNode;
  label: string;
  value: string;
  unit?: string;
  sub: string;
  tone: Tone;
  tag: string;
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon stat-icon-${tone}`}>{icon}</div>
      <div className="stat-label">{label}</div>
      <div className="stat-value">
        {value}
        {unit && <span className="stat-unit">{unit}</span>}
      </div>
      <div className="stat-sub">{sub}</div>
      <div className={`stat-tag stat-tag-${tone}`}>
        <span className="stat-tag-dot" />
        {tag}
      </div>
    </div>
  );
}
