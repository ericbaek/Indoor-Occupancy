import type { RadarDevice, BlePosition } from "../data";
import { isRecentlySeen, timeAgoLabel } from "../lib/sensorHealth";
import "./SensorTable.css";

// Staleness windows, tuned per sensor type based on how it actually
// reports (see sensorHealth.ts). Not user-configurable — these reflect
// real reporting cadence, not a display preference like the CO2 chart
// threshold in Settings.
const RADAR_STALE_MS = 15_000; // continuous mmWave polling (will go offline after 15 sec of inactivity)
const CO2_STALE_MS = 30_000; // continuous SCD41 polling (will go offline after 30 sec of inactivity)
const PIR_STALE_MS = 60_000; // event-driven (will go offline after 1 minute of inactivity)
const BLE_STALE_MS = 3_000; // slightly above the backend's 2s rssi_window_seconds (will go offline after 3 sec of inactivity)

// Mirrors ANCHOR_POSITIONS keys in backend/app/ble_config.py. There's no
// API endpoint that lists configured anchors, so this is hand-kept in
// sync \u2014 update if a teammate adds/renames an anchor server-side.
const KNOWN_BLE_ANCHORS = ["anchor-left", "anchor-right", "anchor-back"] as const;

type SensorStatus = "online" | "offline" | "unknown";

type SensorRow = {
  node: string;
  type: string;
  detail: string;
  lastSeen: string | null;
  /** Overrides the computed "Xs ago" label \u2014 used when lastSeen genuinely can't be known (see BLE rows). */
  lastSeenLabel?: string;
  status: SensorStatus;
};

function buildBleAnchorRows(bleTagsFull: BlePosition[]): SensorRow[] {
  return KNOWN_BLE_ANCHORS.map((anchorId) => {
    // Look for any currently-active tag whose smoothed scanner_rssi
    // includes this anchor within the last few seconds \u2014 the only
    // signal we have, since there's no per-anchor heartbeat endpoint.
    const heardBy = bleTagsFull.find(
      (tag) => anchorId in (tag.scanner_rssi ?? {}) && isRecentlySeen(tag.last_seen_at, BLE_STALE_MS)
    );

    if (heardBy) {
      return {
        node: anchorId,
        type: "BLE anchor",
        detail: `${heardBy.scanner_rssi[anchorId]} dBm (via ${heardBy.tag_id})`,
        lastSeen: heardBy.last_seen_at,
        status: "online" as SensorStatus,
      };
    }

    return {
      node: anchorId,
      type: "BLE anchor",
      detail: "No tag nearby to confirm",
      lastSeen: null,
      lastSeenLabel: "Unknown",
      status: "unknown" as SensorStatus,
    };
  });
}

function buildRows(
  radarDevices: RadarDevice[],
  co2Ppm: number | null,
  co2DeviceId: string | null,
  lastEnvironmentUpdateAt: string | null,
  lastOccupancyEventAt: string | null,
  lastEventType: "entry" | "exit" | null,
  bleTagsFull: BlePosition[]
): SensorRow[] {
  const rows: SensorRow[] = [];

  // PIR is a single physical doorway sensor \u2014 not two separate
  // in/out sensors \u2014 that reports one event stream tagged "entry" or
  // "exit". "Online" here means "is the sensor actually sending data",
  // same as every other row; it deliberately does NOT mean "is someone
  // currently inside" \u2014 that's an occupancy STATE (shown in the detail
  // column below), not a connectivity signal. Conflating the two would
  // make "Offline" ambiguous between "sensor broken" and "nobody's
  // walked through lately", which is a bad failure mode to read at a
  // glance.
  const directionDetail =
    lastEventType === "entry" ? "Last: Entry" : lastEventType === "exit" ? "Last: Exit" : "No events received yet";
  rows.push({
    node: "PIR-DOORWAY",
    type: "PIR (entry/exit)",
    detail: directionDetail,
    lastSeen: lastOccupancyEventAt,
    status: isRecentlySeen(lastOccupancyEventAt, PIR_STALE_MS) ? "online" : "offline",
  });

  for (const dev of radarDevices) {
    rows.push({
      node: dev.device_id,
      type: "mmWave (RD-03D)",
      detail: `${dev.target_count} target${dev.target_count === 1 ? "" : "s"}`,
      lastSeen: dev.received_at,
      status: isRecentlySeen(dev.received_at, RADAR_STALE_MS) ? "online" : "offline",
    });
  }

  // There's exactly one physical CO2 sensor in the real system, so this is
  // always a single row \u2014 driven by the same aggregated status the
  // Dashboard's CO2 StatCard uses (/api/occupancy/status), not a per-device
  // list. That also means stale/leftover device_ids from old test runs
  // never show up here as permanent ghost rows.
  rows.push({
    node: co2DeviceId ?? "CO2 sensor",
    type: "CO2 (SCD41)",
    detail: co2Ppm !== null ? `${co2Ppm} ppm` : "No readings yet",
    lastSeen: lastEnvironmentUpdateAt,
    status: isRecentlySeen(lastEnvironmentUpdateAt, CO2_STALE_MS) ? "online" : "offline",
  });

  rows.push(...buildBleAnchorRows(bleTagsFull));

  return rows;
}

export default function SensorTable({
  radarDevices,
  co2Ppm,
  co2DeviceId,
  lastEnvironmentUpdateAt,
  lastOccupancyEventAt,
  lastEventType,
  bleTagsFull,
}: {
  radarDevices: RadarDevice[];
  co2Ppm: number | null;
  co2DeviceId: string | null;
  lastEnvironmentUpdateAt: string | null;
  lastOccupancyEventAt: string | null;
  lastEventType: "entry" | "exit" | null;
  bleTagsFull: BlePosition[];
}) {
  const rows = buildRows(
    radarDevices,
    co2Ppm,
    co2DeviceId,
    lastEnvironmentUpdateAt,
    lastOccupancyEventAt,
    lastEventType,
    bleTagsFull
  );
  const onlineCount = rows.filter((r) => r.status === "online").length;

  return (
    <div className="sensor-card">
      <div className="chart-title">Sensor node status</div>
      <div className="chart-sub" style={{ marginBottom: 14 }}>
        {`${onlineCount}/${rows.length} online \u00b7 based on real backend readings, not mock data`}
      </div>

      <div className="sensor-table">
        <div className="sensor-row sensor-row-head">
          <span>Node</span>
          <span>Type</span>
          <span>Latest reading</span>
          <span>Last seen</span>
          <span>Status</span>
        </div>
        {rows.map((r) => (
          <div key={r.node} className="sensor-row">
            <span className="sensor-id">{r.node}</span>
            <span>{r.type}</span>
            <span className="sensor-mono">{r.detail}</span>
            <span className="sensor-mono">{r.lastSeenLabel ?? timeAgoLabel(r.lastSeen)}</span>
            <span className={`sensor-status sensor-status-${r.status}`}>
              <span className="sensor-status-dot" />
              {r.status === "online" ? "Online" : r.status === "offline" ? "Offline" : "Unknown"}
            </span>
          </div>
        ))}
      </div>

      <p className="sensor-ble-note">
        {`BLE anchor status is inferred from active tag proximity (no per-anchor heartbeat endpoint exists yet) \u2014 "Unknown" means no tag was nearby to confirm the anchor is alive, not that it's offline.`}
      </p>
    </div>
  );
}