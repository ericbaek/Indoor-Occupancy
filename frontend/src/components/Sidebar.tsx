import { LayoutGrid, DoorOpen, Radar, BellRing, FileBarChart, Settings, ShieldCheck } from "lucide-react";
import "./Sidebar.css";

const NAV = [
  { label: "Dashboard", icon: LayoutGrid, active: true },
  { label: "Rooms", icon: DoorOpen },
  { label: "Sensors", icon: Radar },
  { label: "Alerts", icon: BellRing },
  { label: "Reports", icon: FileBarChart },
  { label: "Settings", icon: Settings },
];

export default function Sidebar() {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden>
          <span className="brand-ring" />
          <span className="brand-dot" />
        </span>
        <div>
          <div className="brand-name">Sentry</div>
          <div className="brand-sub">Occupancy Intelligence</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ label, icon: Icon, active }) => (
          <button key={label} className={`nav-item${active ? " nav-item-active" : ""}`}>
            <Icon size={17} strokeWidth={2} />
            <span className="nav-item-label">{label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="privacy-card">
          <ShieldCheck size={18} strokeWidth={2} />
          <div className="privacy-title">No cameras. No MAC IDs.</div>
          <p>Occupancy is inferred from CO&#8322;, motion and mmWave signal only &mdash; never identity.</p>
        </div>
        <div className="building-tag">CSE Building &middot; Team Football</div>
      </div>
    </aside>
  );
}
