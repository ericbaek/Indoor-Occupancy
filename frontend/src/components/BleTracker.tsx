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

// Room dimensions (must match backend configuration)
const ROOM_WIDTH = 8.0;
const ROOM_HEIGHT = 5.0;

export default function BleTracker({ tagCount, positions, tagsFull }: BleTrackerProps) {
  return (
    <div className="ble-tracker-card card-base">
      <div className="ble-header">
        <h3 className="card-title">Approximate BLE Tracking</h3>
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
            {/* Background Grid */}
            <defs>
              <pattern id="grid" width="100" height="100" patternUnits="userSpaceOnUse">
                <path d="M 100 0 L 0 0 0 100" fill="none" stroke="var(--border)" strokeWidth="1" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#grid)" />
            <rect width="100%" height="100%" fill="none" stroke="var(--border)" strokeWidth="2" />

            {/* Zone Labels */}
            <text x="16.6%" y="50%" className="zone-label" textAnchor="middle" dominantBaseline="middle">Left</text>
            <text x="50%" y="35%" className="zone-label" textAnchor="middle" dominantBaseline="middle">Centre</text>
            <text x="83.3%" y="50%" className="zone-label" textAnchor="middle" dominantBaseline="middle">Right</text>
            <text x="50%" y="85%" className="zone-label" textAnchor="middle" dominantBaseline="middle">Back</text>

            {/* Tag Markers */}
            {positions.map((pos) => {
              // Clamp visual marker inside room
              const x = Math.max(0, Math.min(pos.x, ROOM_WIDTH));
              const y = Math.max(0, Math.min(pos.y, ROOM_HEIGHT));
              return (
                <g key={pos.tag_id} className="tag-marker" transform={`translate(${x * 100}, ${y * 100})`}>
                  <circle r="12" className="tag-pulse" />
                  <circle r="6" className="tag-dot" />
                  <text x="15" y="4" className="tag-name">{pos.tag_id}</text>
                  <text x="15" y="16" className="tag-coord">({pos.x.toFixed(1)}m, {pos.y.toFixed(1)}m)</text>
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
                
                <div className="ble-tag-info">
                  <div className="ble-info-row">
                    <span className="ble-info-label">Stable Zone:</span>
                    <span className="ble-info-value capitalize">{tag.stable_zone}</span>
                  </div>
                  
                  {tag.position ? (
                    <>
                      <div className="ble-info-row">
                        <span className="ble-info-label">Exp. Position:</span>
                        <span className="ble-info-value">({tag.position.x.toFixed(1)}m, {tag.position.y.toFixed(1)}m)</span>
                      </div>
                      <div className="ble-info-row">
                        <span className="ble-info-label">Confidence:</span>
                        <span className="ble-info-value">{tag.confidence_db}%</span>
                      </div>
                    </>
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
