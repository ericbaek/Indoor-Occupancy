import type { CSSProperties } from "react";
import "./BleTracker.css";
import type { BleAnchorSignal, BleSignalSummary, BleZoneName } from "../data";

interface BleTrackerProps {
  signal: BleSignalSummary;
}

const ZONE_DETAILS: Array<{ id: BleZoneName; label: string }> = [
  { id: "left", label: "LEFT SIDE" },
  { id: "right", label: "RIGHT SIDE" },
];

function zoneStyle(zone: BleAnchorSignal): CSSProperties {
  const score = zone.status === "active" ? zone.signal_score ?? 0 : 0;
  const opacity = zone.status === "active" ? 0.04 + score * 0.0076 : 0.02;
  return {
    background: `linear-gradient(rgba(220, 38, 38, ${opacity}), rgba(220, 38, 38, ${opacity})), var(--paper)`,
  };
}

function comparisonLabel(summary: BleSignalSummary): string {
  if (summary.stronger_zone === "left") return "Left signal is stronger";
  if (summary.stronger_zone === "right") return "Right signal is stronger";
  if (summary.stronger_zone === "balanced") return "Signals are approximately balanced";
  return "Waiting for both anchors";
}

export default function BleTracker({ signal }: BleTrackerProps) {
  return (
    <section className="ble-tracker-card card-base" aria-label="Bluetooth signal-strength heatmap">
      <div className="ble-header">
        <div>
          <h3 className="card-title">Bluetooth Signal Intensity</h3>
          <p className="ble-subtitle">Relative two-anchor RSSI activity · not a person or device count</p>
        </div>
        <span className={`ble-badge ${signal.stronger_zone ? "active" : "inactive"}`}>
          {comparisonLabel(signal)}
        </span>
      </div>

      <div className="ble-heatmap">
        {ZONE_DETAILS.map(({ id, label }) => {
          const zone = signal.zones[id];
          const active = zone.status === "active";
          return (
            <article
              key={id}
              className={`ble-zone ${active ? "ble-zone-active" : "ble-zone-offline"}`}
              style={zoneStyle(zone)}
              aria-label={`${label}: ${active ? `${zone.signal_score} out of 100` : "offline"}`}
            >
              <span className="ble-zone-label">{label}</span>
              {active ? (
                <>
                  <strong className="ble-zone-score">{Math.round(zone.signal_score ?? 0)}</strong>
                  <span className="ble-zone-unit">Signal score / 100</span>
                  <span className="ble-zone-rssi">
                    RSSI: {zone.average_rssi === null ? "No advertisements" : `${zone.average_rssi.toFixed(1)} dBm`}
                  </span>
                  <span className="ble-zone-anchor">{zone.anchor_id}</span>
                </>
              ) : (
                <>
                  <strong className="ble-zone-unavailable">No recent signal data</strong>
                  <span className="ble-zone-anchor">{zone.anchor_id}</span>
                </>
              )}
            </article>
          );
        })}
      </div>

      <p className="ble-note">
        Each anchor uses the median of its strongest nearby BLE signals. Scores are EMA-smoothed and become unavailable
        after {signal.anchor_timeout_seconds} seconds without an anchor update.
      </p>
    </section>
  );
}
