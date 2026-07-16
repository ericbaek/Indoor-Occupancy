import { ChevronDown, Sun } from "lucide-react";
import "./Topbar.css";

export default function Topbar() {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">Dashboard</h1>
        <p className="topbar-sub">Real-time occupancy across CSE teaching spaces</p>
      </div>
      <div className="topbar-actions">
        <button className="icon-btn" aria-label="Toggle theme">
          <Sun size={16} strokeWidth={2} />
        </button>
        <button className="building-select">
          CSE Building
          <ChevronDown size={14} strokeWidth={2} />
        </button>
      </div>
    </header>
  );
}
