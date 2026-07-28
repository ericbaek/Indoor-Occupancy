import { Moon, Sun } from "lucide-react";
import "./Topbar.css";

type TopbarProps = {
  title: string;
  sub: string;
  theme: "light" | "dark";
  onToggleTheme: () => void;
};

export default function Topbar({ title, sub, theme, onToggleTheme }: TopbarProps) {
  const isLight = theme === "light";

  return (
    <header className="topbar">
      <div>
        <h1 className="topbar-title">{title}</h1>
        <p className="topbar-sub">{sub}</p>
      </div>
      <div className="topbar-actions">
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
