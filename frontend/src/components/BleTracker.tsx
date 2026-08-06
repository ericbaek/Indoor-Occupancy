import { useEffect, useState } from "react";
import "./BleTracker.css";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

type ZoneSignal = {
  anchor_id: string;
  zone: "left" | "right";
  status: "active" | "offline";
  average_rssi: number | null;
  signal_score: number | null;
  last_seen_at: string | null;
};

type SignalSummary = {
  measurement: string;
  zones: {
    left: ZoneSignal;
    right: ZoneSignal;
  };
  stronger_zone: "left" | "right" | "balanced" | null;
  anchor_timeout_seconds: number;
  ema_alpha: number;
};

function zoneColour(score: number | null): string {
  const strength = score === null ? 0 : Math.max(0, Math.min(100, score));
  const alpha = strength === 0 ? 0.03 : 0.08 + (strength / 100) * 0.52;
  return `rgba(239, 68, 68, ${alpha})`;
}

function ZonePanel({ label, signal }: { label: string; signal?: ZoneSignal }) {
  const score = signal?.signal_score ?? null;
  return (
    <section
      className={`ble-signal-zone ${signal?.status === "active" ? "active" : "offline"}`}
      style={{ backgroundColor: zoneColour(score) }}
    >
      <h4>{label}</h4>
      <strong>{score === null ? "No signal" : `${score.toFixed(1)}%`}</strong>
      <span>
        {signal?.average_rssi === null || signal?.average_rssi === undefined
          ? "RSSI unavailable"
          : `${signal.average_rssi.toFixed(1)} dBm`}
      </span>
      <small>{signal?.status ?? "offline"}</small>
    </section>
  );
}

export default function BleTracker() {
  const [summary, setSummary] = useState<SignalSummary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let stopped = false;

    async function refresh() {
      try {
        const response = await fetch(`${API_BASE}/bluetooth/signal-strength`);
        if (!response.ok) {
          throw new Error(`Bluetooth API returned ${response.status}`);
        }
        const next = (await response.json()) as SignalSummary;
        if (!stopped) {
          setSummary(next);
          setError(null);
        }
      } catch (reason) {
        if (!stopped) {
          setError(reason instanceof Error ? reason.message : "Bluetooth data unavailable");
        }
      }
    }

    void refresh();
    const timer = window.setInterval(refresh, 1000);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, []);

  const strongerLabel =
    summary?.stronger_zone === "left"
      ? "Left stronger"
      : summary?.stronger_zone === "right"
        ? "Right stronger"
        : summary?.stronger_zone === "balanced"
          ? "Balanced"
          : "Waiting for anchors";

  return (
    <section className="ble-tracker-card">
      <header className="ble-header">
        <div>
          <h3 className="card-title">Bluetooth Signal Heatmap</h3>
          <p className="ble-header-note">Relative RSSI from the left and right anchors</p>
        </div>
        <span className="ble-summary-badge">{strongerLabel}</span>
      </header>

      <div className="ble-signal-grid">
        <ZonePanel label="LEFT ZONE" signal={summary?.zones.left} />
        <ZonePanel label="RIGHT ZONE" signal={summary?.zones.right} />
      </div>

      {error && <p className="ble-error">{error}</p>}
    </section>
  );
}
