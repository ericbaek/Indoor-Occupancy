import "./BleTracker.css";
import type { BlePosition } from "../data";

interface BleTrackerProps {
  tagCount: number;
  zones: Record<string, number>;
  positions: Array<{
    tag_id: string;
    x: number;
    y: number;
    label: string;
  }>;
  tagsFull: BlePosition[];
}

// Room dimensions (must match backend ble_config.ROOM_DIMENSIONS)
const ROOM_WIDTH = 8.0;
const ROOM_HEIGHT = 5.0;

// Zone x-boundaries (must match backend ble_config.ZONE_BOUNDARIES).
// "back" isn't drawn — it needs a 3rd anchor the current 2-anchor rig
// doesn't have, so it's never actually reachable yet.
const ZONE_BANDS: Array<{ zone: string; label: string; xMin: number; xMax: number }> = [
  { zone: "left", label: "Left", xMin: 0, xMax: 2.67 },
  { zone: "centre", label: "Centre", xMin: 2.67, xMax: 5.33 },
  { zone: "right", label: "Right", xMin: 5.33, xMax: 8.0 },
];

function zoneCenterX(zone: string): number {
  const band = ZONE_BANDS.find((b) => b.zone === zone);
  return band ? (band.xMin + band.xMax) / 2 : ROOM_WIDTH / 2;
}

export default function BleTracker({ tagCount, tagsFull }: BleTrackerProps) {
  return (
    <div className="ble-tracker-card card-base">
      <div className="ble-header">
        <div>
          <h3 className="card-title">Approximate BLE Tracking</h3>
          <p className="ble-header-note">2-anchor setup &middot; left / centre / right zone only</p>
        </div>
        <span className={`ble-badge ${tagCount > 0 ? "active" : "inactive"}`}>
          {tagCount} Active Tag{tagCount !== 1 && "s"}
        </span>
      </div>

      <div className="ble-content">
        <div className="ble-map-container">
          <svg
            className="ble-map"
            viewBox={`0 0 ${ROOM_WIDTH * 100} ${ROOM_HEIGHT * 100}`}
            preserveAspectRatio="xMidYMid meet"
          >
            {/* Zone bands — the unit of confidence this rig can actually
                deliver right now, drawn as regions rather than points. */}
            {ZONE_BANDS.map((band) => {
              const occupiedByCount = tagsFull.filter((t) => t.stable_zone === band.zone).length;
              return (
                <g key={band.zone}>
                  <rect
                    x={band.xMin * 100}
                    y={0}
                    width={(band.xMax - band.xMin) * 100}
                    height={ROOM_HEIGHT * 100}
                    className={`zone-band${occupiedByCount > 0 ? " zone-band-occupied" : ""}`}
                  />
                  <text
                    x={((band.xMin + band.xMax) / 2) * 100}
                    y="50%"
                    className="zone-label"
                    textAnchor="middle"
                    dominantBaseline="middle"
                  >
                    {band.label}
                  </text>
                </g>
              );
            })}
            {/* Zone divider lines */}
            {[2.67, 5.33].map((x) => (
              <line key={x} x1={x * 100} y1={0} x2={x * 100} y2={ROOM_HEIGHT * 100} className="zone-divider" />
            ))}

            {/* Tag markers — placed at the centre of their detected zone,
                not at the raw (x, y) reading. With only 2 anchors, x is
                noisy and y never moves, so plotting the raw point would
                read as more precise than the data actually is. */}
            {tagsFull.map((tag, i) => {
              const cx = zoneCenterX(tag.stable_zone);
              // Stack multiple tags in the same zone so they don't overlap.
              const sameZoneBefore = tagsFull.slice(0, i).filter((t) => t.stable_zone === tag.stable_zone).length;
              const cy = ROOM_HEIGHT / 2 + sameZoneBefore * 0.6;
              return (
                <g key={tag.tag_id} className="tag-marker" transform={`translate(${cx * 100}, ${cy * 100})`}>
                  <circle r="12" className="tag-pulse" />
                  <circle r="6" className="tag-dot" />
                  <text x="15" y="4" className="tag-name">{tag.tag_id}</text>
                  <text x="15" y="16" className="tag-zone-caption">{tag.stable_zone} zone</text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="ble-list">
          {tagsFull.length === 0 ? (
            <div className="ble-empty">No participating tags detected.</div>
          ) : (
            tagsFull.map((tag) => (
              <div key={tag.tag_id} className="ble-tag-detail">
                <div className="ble-tag-header">
                  <span className="ble-tag-id">{tag.tag_id}</span>
                  <span className={`ble-status-dot ${tag.status}`} title={tag.status} />
                </div>

                <div className="ble-zone-primary">
                  <span className={`zone-badge zone-badge-${tag.stable_zone}`}>{tag.stable_zone}</span>
                </div>

                <div className="ble-tag-info">
                  {tag.position ? (
                    <div className="ble-info-row">
                      <span className="ble-info-label">Raw estimate:</span>
                      <span className="ble-info-value dim">
                        ({tag.position.x.toFixed(1)}m, {tag.position.y.toFixed(1)}m) &middot; {tag.confidence_db}% &middot; experimental
                      </span>
                    </div>
                  ) : (
                    <div className="ble-info-row">
                      <span className="ble-info-label">Position:</span>
                      <span className="ble-info-value dim">Insufficient data</span>
                    </div>
                  )}

                  <div className="ble-info-row">
                    <span className="ble-info-label">Last seen:</span>
                    <span className="ble-info-value dim">
                      {new Date(tag.last_seen_at).toLocaleTimeString()}
                    </span>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}