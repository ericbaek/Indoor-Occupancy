import type { RadarDevice, BleSignalSummary } from "../data";
import { isRecentlySeen, timeAgoLabel } from "../lib/sensorHealth";
import "./SensorTable.css";

const RADAR_STALE_MS = 15_000;
const CO2_STALE_MS = 30_000;
const PIR_STALE_MS = 60_000;

type SensorStatus = "online" | "offline" | "unknown";

type SensorRow = {
  node: string;
  type: string;
  detail: string;
  lastSeen: string | null;
  lastSeenLabel?: string;
  status: SensorStatus;
};

function buildBleAnchorRows(bleSignal: BleSignalSummary | null): SensorRow[] {
  if (!bleSignal) {
    return [
      { node: "left-anchor", type: "BLE anchor", detail: "No data yet", lastSeen: null, lastSeenLabel: "Unknown", status: "unknown" },
      { node: "right-anchor", type: "BLE anchor", detail: "No data yet", lastSeen: null, lastSeenLabel: "Unknown", status: "unknown" },
    ];
  }

  return (["left", "right"] as const).map((zoneName) => {
    const zone = bleSignal.zones[zoneName];
    if (zone.status === "active") {
      return {
        node: zone.anchor_id,
        type: "BLE anchor",
        detail: zone.signal_score !== null ? `Signal score ${Math.round(zone.signal_score)}` : "Active",
        lastSeen: zone.last_seen_at,
        status: "online" as SensorStatus,
      };
    }
    return {
      node: zone.anchor_id,
      type: "BLE anchor",
      detail: "No recent signal",
      lastSeen: zone.last_seen_at,
      lastSeenLabel: zone.last_seen_at ? undefined : "Unknown",
      status: "offline" as SensorStatus,
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
  bleSignal: BleSignalSummary | null
): SensorRow[] {
  const rows: SensorRow[] = [];

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

  rows.push({
    node: co2DeviceId ?? "CO2 sensor",
    type: "CO2 (SCD41)",
    detail: co2Ppm !== null ? `${co2Ppm} ppm` : "No readings yet",
    lastSeen: lastEnvironmentUpdateAt,
    status: isRecentlySeen(lastEnvironmentUpdateAt, CO2_STALE_MS) ? "online" : "offline",
  });

  rows.push(...buildBleAnchorRows(bleSignal));

  return rows;
}

export default function SensorTable({
  radarDevices,
  co2Ppm,
  co2DeviceId,
  lastEnvironmentUpdateAt,
  lastOccupancyEventAt,
  lastEventType,
  bleSignal,
}: {
  radarDevices: RadarDevice[];
  co2Ppm: number | null;
  co2DeviceId: string | null;
  lastEnvironmentUpdateAt: string | null;
  lastOccupancyEventAt: string | null;
  lastEventType: "entry" | "exit" | null;
  bleSignal: BleSignalSummary | null;
}) {
  const rows = buildRows(
    radarDevices,
    co2Ppm,
    co2DeviceId,
    lastEnvironmentUpdateAt,
    lastOccupancyEventAt,
    lastEventType,
    bleSignal
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
