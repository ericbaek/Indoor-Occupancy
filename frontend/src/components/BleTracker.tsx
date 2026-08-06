import "./BleTracker.css";
import type { BlePosition } from "../data";
import { formatDistanceMetres, type Units } from "../hooks/usePreferences";

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
  units: Units;
}

// Room dimensions (must match backend ble_config.ROOM_DIMENSIONS)
const ROOM_WIDTH = 8.0;
const ROOM_HEIGHT = 5.0;
const HALF_X = ROOM_WIDTH / 2;

type Side = "left" | "right";

/**
 * Only two sides now, not three zones \u2014 "centre" is deliberately gone
 * from the UI. The backend can still classify a tag as stable_zone
 * "centre" (its 3-zone threshold logic in ble_config.py is untouched),
 * but the frontend no longer renders that distinction: any tag is bucketed
 * into whichever half of the room its raw x sits in. This is a display
 * choice only, not a backend change.
 */
function resolveSide(tag: BlePosition): Side | null {
  if (tag.position) {
    return tag.position.x < HALF_X ? "left" : "right";
  }
  // No raw position (insufficient data) \u2014 fall back to the backend's
  // zone label only if it's unambiguously left/right; a backend "centre"
  // classification with no position data can't be resolved to a side.
  if (tag.stable_zone === "left" || tag.stable_zone === "right") {
    return tag.stable_zone;
  }
  return null;
}

/** 0 (no signal) to 1 (strongest tag on that side) drives the heatmap glow intensity. */
function sideIntensity(tags: BlePosition[], side: Side): number {
  const onSide = tags.filter((t) => resolveSide(t) === side);
  if (onSide.length === 0) return 0;
  const maxConfidence = Math.max(...onSide.map((t) => t.confidence_db));
  // Floor at 0.35 so presence is always visibly "hot" even at low
  // confidence \u2014 this is a presence glow, not a confidence gauge.
  return Math.max(0.35, Math.min(1, maxConfidence / 100));
}

export default function BleTracker({ tagCount, tagsFull, units }: BleTrackerProps) {
  const leftIntensity = sideIntensity(tagsFull, "left");
  const rightIntensity = sideIntensity(tagsFull, "right");

  return (
    <div className="ble-tracker-card card-base">
      <div className="ble-header">
        <div>
          <h3 className="card-title">Approximate BLE Tracking</h3>
          <p className="ble-header-note">2-anchor setup &middot; left / right side only</p>
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
            <defs>
              <radialGradient id="heatGlowLeft" cx="50%" cy="50%" r="65%">
                <stop offset="0%" stopColor="var(--signal)" stopOpacity="0.75" />
                <stop offset="55%" stopColor="var(--signal)" stopOpacity="0.28" />
                <stop offset="100%" stopColor="var(--signal)" stopOpacity="0" />
              </radialGradient>
              <radialGradient id="heatGlowRight" cx="50%" cy="50%" r="65%">
                <stop offset="0%" stopColor="var(--signal)" stopOpacity="0.75" />
                <stop offset="55%" stopColor="var(--signal)" stopOpacity="0.28" />
                <stop offset="100%" stopColor="var(--signal)" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Two halves, not three zones. Each half is a plain outline;
                the heatmap glow (below) is the only thing that indicates
                presence, scaled by whichever side currently has a tag. */}
            <rect x={0} y={0} width={HALF_X * 100} height={ROOM_HEIGHT * 100} className="zone-band" />
            <rect x={HALF_X * 100} y={0} width={HALF_X * 100} height={ROOM_HEIGHT * 100} className="zone-band" />
            <line x1={HALF_X * 100} y1={0} x2={HALF_X * 100} y2={ROOM_HEIGHT * 100} className="zone-divider" />

            <text x={(HALF_X / 2) * 100} y="50%" className="zone-label" textAnchor="middle" dominantBaseline="middle">
              Left
            </text>
            <text
              x={(HALF_X + HALF_X / 2) * 100}
              y="50%"
              className="zone-label"
              textAnchor="middle"
              dominantBaseline="middle"
            >
              Right
            </text>

            {/* Heatmap glow \u2014 fills the whole active half rather than a
                precise point. With only 2 anchors, raw (x, y) is too noisy
                to plot a tight localized blob honestly (see the tag-marker
                comment below); a room-half glow is the level of precision
                this rig can actually back up. */}
            {leftIntensity > 0 && (
              <rect
                x={0}
                y={0}
                width={HALF_X * 100}
                height={ROOM_HEIGHT * 100}
                fill="url(#heatGlowLeft)"
                opacity={leftIntensity}
                className="heat-glow"
              />
            )}
            {rightIntensity > 0 && (
              <rect
                x={HALF_X * 100}
                y={0}
                width={HALF_X * 100}
                height={ROOM_HEIGHT * 100}
                fill="url(#heatGlowRight)"
                opacity={rightIntensity}
                className="heat-glow"
              />
            )}

            {/* Tag markers \u2014 placed at the centre of their resolved side,
                not at the raw (x, y) reading. With only 2 anchors, x is
                noisy and y never moves, so plotting the raw point would
                read as more precise than the data actually is. */}
            {tagsFull.map((tag, i) => {
              const side = resolveSide(tag);
              if (!side) return null;
              const cx = side === "left" ? HALF_X / 2 : HALF_X + HALF_X / 2;
              // Stack multiple tags on the same side so they don't overlap.
              const sameSideBefore = tagsFull.slice(0, i).filter((t) => resolveSide(t) === side).length;
              const cy = ROOM_HEIGHT / 2 + sameSideBefore * 0.6;
              return (
                <g key={tag.tag_id} className="tag-marker" transform={`translate(${cx * 100}, ${cy * 100})`}>
                  <circle r="12" className="tag-pulse" />
                  <circle r="6" className="tag-dot" />
                  <text x="15" y="4" className="tag-name">{tag.tag_id}</text>
                  <text x="15" y="16" className="tag-zone-caption">{side} side</text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="ble-list">
          {tagsFull.length === 0 ? (
            <div className="ble-empty">No participating tags detected.</div>
          ) : (
            tagsFull.map((tag) => {
              const side = resolveSide(tag);
              return (
                <div key={tag.tag_id} className="ble-tag-detail">
                  <div className="ble-tag-header">
                    <span className="ble-tag-id">{tag.tag_id}</span>
                    <span className={`ble-status-dot ${tag.status}`} title={tag.status} />
                  </div>

                  <div className="ble-zone-primary">
                    {side ? (
                      <span className={`zone-badge zone-badge-${side}`}>{side}</span>
                    ) : (
                      <span className="zone-badge zone-badge-unknown">unresolved</span>
                    )}
                  </div>

                  <div className="ble-tag-info">
                    {tag.position ? (
                      <div className="ble-info-row">
                        <span className="ble-info-label">Raw estimate:</span>
                        <span className="ble-info-value dim">
                          ({formatDistanceMetres(tag.position.x, units)}, {formatDistanceMetres(tag.position.y, units)}) &middot; {tag.confidence_db}% &middot; experimental
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
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}