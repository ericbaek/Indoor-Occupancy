import "./BleTracker.css";
import type { BleSignalSummary, BleZoneSnapshot } from "../data";

interface BleTrackerProps {
  signal: BleSignalSummary | null;
}

// Room dimensions (must match backend ble_config.ROOM_DIMENSIONS, if/when
// that's reintroduced). Purely for the SVG viewBox split — the backend
// itself no longer models room geometry, just left/right anchors.
const ROOM_WIDTH = 8.0;
const ROOM_HEIGHT = 5.0;
const HALF_X = ROOM_WIDTH / 2;

/**
 * 0 (no/offline signal) to 1 (strongest possible) drives the heatmap glow.
 *
 * This is intentionally NOT linear with signal_score. A gentle exponent
 * (>1) pushes weak signals down toward "barely there" and lets strong
 * signals hold onto most of their brightness, so a real difference in
 * strength (e.g. 85 vs 30) reads as a drastic visual difference instead
 * of two similarly-glowy blobs. There's a tiny floor (0.05) purely so an
 * active-but-weak zone is distinguishable from a fully offline one.
 */
function zoneIntensity(zone: BleZoneSnapshot | undefined): number {
  if (!zone || zone.status !== "active" || zone.signal_score === null) return 0;
  const normalized = Math.max(0, Math.min(1, zone.signal_score / 100));
  const shaped = Math.pow(normalized, 1.8);
  return Math.max(0.05, shaped);
}

/** Glow radius (in local SVG units) scales with intensity too, so a strong
 * signal is a big blob and a weak one is a tight, small dot — the size
 * difference reinforces the opacity difference instead of relying on it alone. */
function zoneRadius(intensity: number): number {
  return 55 + intensity * 230;
}

function formatScore(zone: BleZoneSnapshot | undefined): string {
  if (!zone || zone.status !== "active" || zone.signal_score === null) return "\u2014";
  return `${Math.round(zone.signal_score)}`;
}

function formatRssi(zone: BleZoneSnapshot | undefined): string {
  if (!zone || zone.status !== "active" || zone.average_rssi === null) return "\u2014";
  return `${zone.average_rssi.toFixed(1)} dBm`;
}

function formatLastSeen(zone: BleZoneSnapshot | undefined): string {
  if (!zone?.last_seen_at) return "Never";
  return new Date(zone.last_seen_at).toLocaleTimeString();
}

const ZONE_LABEL: Record<"left" | "right", string> = { left: "Left", right: "Right" };

export default function BleTracker({ signal }: BleTrackerProps) {
  const left = signal?.zones.left;
  const right = signal?.zones.right;
  const leftIntensity = zoneIntensity(left);
  const rightIntensity = zoneIntensity(right);
  const activeCount = [left, right].filter((z) => z?.status === "active").length;

  // A "drastic" gap is when the two intensities differ by a lot — that's
  // when we add a pulsing ring around the stronger side to make the
  // imbalance unmistakable, rather than just leaning on the base glow.
  const intensityGap = Math.abs(leftIntensity - rightIntensity);
  const isDrasticGap = intensityGap > 0.35;
  const leftIsDominant = isDrasticGap && leftIntensity > rightIntensity;
  const rightIsDominant = isDrasticGap && rightIntensity > leftIntensity;

  return (
    <div className="ble-tracker-card card-base">
      <div className="ble-header">
        <div>
          <h3 className="card-title">Approximate BLE Tracking</h3>
          <p className="ble-header-note">2-anchor setup &middot; left / right signal strength</p>
        </div>
        <span className={`ble-badge ${activeCount > 0 ? "active" : "inactive"}`}>
          {activeCount} Active Anchor{activeCount !== 1 && "s"}
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
              <radialGradient id="heatCore" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="var(--signal)" stopOpacity="0.9" />
                <stop offset="100%" stopColor="var(--signal)" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Two halves, one per anchor. There's no per-person position
                data anymore — the glow reflects relative signal strength
                on each side, not a located point. */}
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

            {leftIntensity > 0 && (
              <g className={leftIsDominant ? "heat-zone heat-zone-dominant" : "heat-zone"}>
                {leftIsDominant && (
                  <circle
                    cx={(HALF_X / 2) * 100}
                    cy={ROOM_HEIGHT * 50}
                    r={zoneRadius(leftIntensity)}
                    className="heat-pulse-ring"
                  />
                )}
                <circle
                  cx={(HALF_X / 2) * 100}
                  cy={ROOM_HEIGHT * 50}
                  r={zoneRadius(leftIntensity)}
                  fill="url(#heatGlowLeft)"
                  opacity={leftIntensity}
                  className="heat-glow"
                />
                <circle
                  cx={(HALF_X / 2) * 100}
                  cy={ROOM_HEIGHT * 50}
                  r={zoneRadius(leftIntensity) * 0.35}
                  fill="url(#heatCore)"
                  opacity={leftIntensity}
                  className="heat-glow"
                />
              </g>
            )}
            {rightIntensity > 0 && (
              <g className={rightIsDominant ? "heat-zone heat-zone-dominant" : "heat-zone"}>
                {rightIsDominant && (
                  <circle
                    cx={(HALF_X + HALF_X / 2) * 100}
                    cy={ROOM_HEIGHT * 50}
                    r={zoneRadius(rightIntensity)}
                    className="heat-pulse-ring"
                  />
                )}
                <circle
                  cx={(HALF_X + HALF_X / 2) * 100}
                  cy={ROOM_HEIGHT * 50}
                  r={zoneRadius(rightIntensity)}
                  fill="url(#heatGlowRight)"
                  opacity={rightIntensity}
                  className="heat-glow"
                />
                <circle
                  cx={(HALF_X + HALF_X / 2) * 100}
                  cy={ROOM_HEIGHT * 50}
                  r={zoneRadius(rightIntensity) * 0.35}
                  fill="url(#heatCore)"
                  opacity={rightIntensity}
                  className="heat-glow"
                />
              </g>
            )}
          </svg>
        </div>

        <div className="ble-list">
          {!signal ? (
            <div className="ble-empty">No Bluetooth data yet.</div>
          ) : (
            (["left", "right"] as const).map((zoneName) => {
              const zone = signal.zones[zoneName];
              return (
                <div key={zoneName} className="ble-tag-detail">
                  <div className="ble-tag-header">
                    <span className="ble-tag-id">{ZONE_LABEL[zoneName]} anchor</span>
                    <span
                      className={`ble-status-dot ${zone.status === "active" ? "inside" : "outside"}`}
                      title={zone.status}
                    />
                  </div>

                  <div className="ble-zone-primary">
                    <span className={`zone-badge zone-badge-${zoneName}`}>{zone.status}</span>
                    {signal.stronger_zone === zoneName && (
                      <span className="zone-badge zone-badge-unknown" style={{ marginLeft: 6 }}>
                        stronger side
                      </span>
                    )}
                  </div>

                  <div className="ble-tag-info">
                    <div className="ble-info-row">
                      <span className="ble-info-label">Signal score:</span>
                      <span className="ble-info-value dim">{formatScore(zone)} / 100</span>
                    </div>
                    <div className="ble-info-row">
                      <span className="ble-info-label">Avg RSSI:</span>
                      <span className="ble-info-value dim">{formatRssi(zone)}</span>
                    </div>
                    <div className="ble-info-row">
                      <span className="ble-info-label">Anchor ID:</span>
                      <span className="ble-info-value dim">{zone.anchor_id}</span>
                    </div>
                    <div className="ble-info-row">
                      <span className="ble-info-label">Last seen:</span>
                      <span className="ble-info-value dim">{formatLastSeen(zone)}</span>
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