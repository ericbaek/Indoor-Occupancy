import { ChevronDown, Sun } from "lucide-react";
import "./Topbar.css";

export default function Topbar({ title, sub }: { title: string; sub: string }) {
  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-sub">{sub}</p>
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