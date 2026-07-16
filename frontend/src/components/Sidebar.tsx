import { LayoutGrid, DoorOpen, Radar, BellRing, FileBarChart, Settings, ShieldCheck } from "lucide-react";
import "./Sidebar.css";

export const NAV_ITEMS = ["Dashboard", "Rooms", "Sensors", "Alerts", "Reports", "Settings"] as const;
export type NavItem = (typeof NAV_ITEMS)[number];

const NAV = [
  { label: "Dashboard", icon: LayoutGrid },
  { label: "Rooms", icon: DoorOpen },
  { label: "Sensors", icon: Radar },
  { label: "Alerts", icon: BellRing },
  { label: "Reports", icon: FileBarChart },
  { label: "Settings", icon: Settings },
] satisfies { label: NavItem; icon: typeof LayoutGrid }[];

export default function Sidebar({
  active,
  onNavigate,
}: {
  active: NavItem;
  onNavigate: (item: NavItem) => void;
}) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden>
          <span className="brand-ring" />
          <span className="brand-dot" />
        </span>
        <div>
          <div className="brand-name">Room Sense</div>
          <div className="brand-sub">Occupancy Intelligence</div>
        </div>
      </div>

      <nav className="sidebar-nav">
        {NAV.map(({ label, icon: Icon }) => (
          <button
            key={label}
            className={`nav-item${label === active ? " nav-item-active" : ""}`}
            onClick={() => onNavigate(label)}
            aria-current={label === active ? "page" : undefined}
          >
            <Icon size={17} strokeWidth={2} />
            <span className="nav-item-label">{label}</span>
          </button>
        ))}
      </nav>
    </aside>
  );
}