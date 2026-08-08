import { useEffect, useState } from "react";
import { ShieldCheck, ShieldAlert, Footprints, Radar } from "lucide-react";
import "./DetectionStatusCard.css";

function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  if (totalSeconds < 60) return `${totalSeconds}s`;
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes < 60) return `${minutes}m ${seconds}s`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ${minutes % 60}m`;
}

export default function DetectionStatusCard({
  status,
  occupancy,
  radarPresence,
  radarTargetCount,
  mismatchStartedAt,
}: {
  status: "confirmed" | "uncertain" | null;
  occupancy: number;
  radarPresence: boolean;
  radarTargetCount: number;
  mismatchStartedAt: string | null;
}) {
  // Update the uncertainty duration every second.
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (status !== "uncertain" || !mismatchStartedAt) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [status, mismatchStartedAt]);

  const isConfirmed = status === "confirmed";
  const isUncertain = status === "uncertain";
  const mismatchDuration =
    isUncertain && mismatchStartedAt
      ? formatDuration(now - new Date(mismatchStartedAt).getTime())
      : null;

  return (
    <div className={`detection-card detection-card-${status ?? "unknown"}`}>
      <div className={`stat-icon stat-icon-${isConfirmed ? "signal" : isUncertain ? "amber" : "neutral"}`}>
        {isConfirmed ? <ShieldCheck size={17} strokeWidth={2} /> : <ShieldAlert size={17} strokeWidth={2} />}
      </div>

      <div className="stat-label">Detection status</div>
      <div className="stat-value">
        {status === "confirmed" ? "Confirmed" : status === "uncertain" ? "Uncertain" : "—"}
      </div>

      <div className="detection-breakdown">
        <div className="detection-row">
          <Footprints size={14} strokeWidth={2} />
          <span>PIR: {occupancy > 0 ? `${occupancy} present` : "empty"}</span>
        </div>
        <div className="detection-row">
          <Radar size={14} strokeWidth={2} />
          <span>Radar: {radarPresence ? `${radarTargetCount} target${radarTargetCount === 1 ? "" : "s"}` : "clear"}</span>
        </div>
      </div>

      <div className={`stat-tag stat-tag-${isConfirmed ? "signal" : isUncertain ? "amber" : "neutral"}`}>
        <span className="stat-tag-dot" />
        {isConfirmed && "PIR + radar agree"}
        {isUncertain && `Mismatch \u2014 ${mismatchDuration}`}
        {!status && "No data yet"}
      </div>
    </div>
  );
}
