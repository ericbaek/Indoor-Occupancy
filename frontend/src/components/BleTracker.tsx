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

/** 0 (no/offline signal) to 1 (strongest possible) drives the heatmap glow intensity. */
function zoneIntensity(zone: BleZoneSnapshot | undefined): number {
  if (!zone || zone.status !== "active" || zone.signal_score === null) return 0;
  // Floor at 0.35 so an active zone is always visibly "hot", even at a
  // weak signal_score — this is a presence glow, not a precise gauge.
  return Math.max(0.35, Math.min(1, zone.signal_score / 100));
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