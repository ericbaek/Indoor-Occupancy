import "./BleTracker.css";
import type { BleTagState, BleZoneName } from "../data";

interface BleTrackerProps {
  tagCount: number;
  zones: Record<BleZoneName, number>;
  tags: BleTagState[];
}

const ZONE_DETAILS: Array<{ id: BleZoneName; label: string; anchor: string }> = [
  { id: "left", label: "LEFT ZONE", anchor: "Left laptop" },
  { id: "right", label: "RIGHT ZONE", anchor: "Right laptop" },
];

function intensity(count: number): string {
  if (count === 0) return "empty";
  if (count === 1) return "low";
  if (count <= 3) return "medium";
  return "high";
}

function formatRssi(tag: BleTagState, zone: BleZoneName): string {
  const rssi = tag.scanner_rssi[`anchor-${zone}`];
  return rssi === undefined ? "--" : `${rssi.toFixed(1)} dBm`;
}

export default function BleTracker({ tagCount, zones, tags }: BleTrackerProps) {
  const unassigned = tags.filter((tag) => tag.current_zone === "unknown");

  return (
    <section className="ble-tracker-card card-base" aria-label="Bluetooth room heatmap">
      <div className="ble-header">
        <div>
          <h3 className="card-title">Bluetooth Room Distribution</h3>
          <p className="ble-subtitle">Two-zone estimate from smoothed laptop RSSI</p>
        </div>
        <span className={`ble-badge ${tagCount > 0 ? "active" : "inactive"}`}>
          {tagCount} active tag{tagCount === 1 ? "" : "s"}
        </span>
      </div>

      <div className="ble-heatmap">
        {ZONE_DETAILS.map((zone) => {
          const count = zones[zone.id] ?? 0;
          const zoneTags = tags.filter((tag) => tag.current_zone === zone.id);
          return (
            <article
              key={zone.id}
              className={`ble-zone ble-zone-${intensity(count)}`}
              aria-label={`${zone.label}: ${count} tags`}
            >
              <span className="ble-zone-label">{zone.label}</span>
              <strong className="ble-zone-count">{count}</strong>
              <span className="ble-zone-unit">tag{count === 1 ? "" : "s"}</span>
              <span className="ble-zone-anchor">{zone.anchor}</span>

              <div className="ble-zone-tags">
                {zoneTags.map((tag) => (
                  <span className="ble-tag-chip" key={tag.tag_id}>
                    <span>{tag.tag_id}</span>
                    <span>{formatRssi(tag, zone.id)}</span>
                  </span>
                ))}
              </div>
            </article>
          );
        })}
      </div>

      {unassigned.length > 0 && (
        <p className="ble-unassigned">
          Waiting for both anchors: {unassigned.map((tag) => tag.tag_id).join(", ")}
        </p>
      )}
      <p className="ble-note">
        The opposite anchor must become at least 5 dBm stronger before a tag switches sides.
      </p>
    </section>
  );
}
