import type { LucideIcon } from "lucide-react";
import "./PlaceholderPage.css";

export default function PlaceholderPage({
  icon: Icon,
  title,
  blurb,
}: {
  icon: LucideIcon;
  title: string;
  blurb: string;
}) {
  return (
    <div className="placeholder-card">
      <div className="placeholder-icon">
        <Icon size={20} strokeWidth={2} />
      </div>
      <div className="placeholder-title">{title}</div>
      <p className="placeholder-blurb">{blurb}</p>
    </div>
  );
}