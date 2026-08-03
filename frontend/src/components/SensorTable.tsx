import type { BleSignalSummary, RadarDevice } from "../data";
import { isRecentlySeen, timeAgoLabel } from "../lib/sensorHealth";
import "./SensorTable.css";

const RADAR_STALE_MS = 15_000;
const CO2_STALE_MS = 30_000;
const PIR_STALE_MS = 60_000;

type SensorStatus = "online" | "offline";

type SensorRow = {
  node: string;
  type: string;
  detail: string;
  lastSeen: string | null;
  status: SensorStatus;
};

function buildBleAnchorRows(bleSignal: BleSignalSummary): SensorRow[] {
  return (["left", "right"] as const).map((zoneName) => {
    const anchor = bleSignal.zones[zoneName];
    if (anchor.status === "active") {
      return {
        node: anchor.anchor_id,
        type: "BLE anchor",
        detail: anchor.average_rssi === null
          ? `Signal ${Math.round(anchor.signal_score ?? 0)}/100 · no advertisements`
          : `Signal ${Math.round(anchor.signal_score ?? 0)}/100 · ${anchor.average_rssi.toFixed(1)} dBm`,
        lastSeen: anchor.last_seen_at,
        status: "online" as SensorStatus,
      };
    }

    return {
      node: anchor.anchor_id,
      type: "BLE anchor",
      detail: "No recent signal data",
      lastSeen: anchor.last_seen_at,
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
  bleSignal: BleSignalSummary
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

  for (const device of radarDevices) {
    rows.push({
      node: device.device_id,
      type: "mmWave (RD-03D)",
      detail: `${device.target_count} target${device.target_count === 1 ? "" : "s"}`,
      lastSeen: device.received_at,
      status: isRecentlySeen(device.received_at, RADAR_STALE_MS) ? "online" : "offline",
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
  bleSignal: BleSignalSummary;
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
  const onlineCount = rows.filter((row) => row.status === "online").length;

  return (
    <div className="sensor-card">
      <div className="chart-title">Sensor node status</div>
      <div className="chart-sub" style={{ marginBottom: 14 }}>
        {`${onlineCount}/${rows.length} online · based on real backend readings, not mock data`}
      </div>

      <div className="sensor-table">
        <div className="sensor-row sensor-row-head">
          <span>Node</span>
          <span>Type</span>
          <span>Latest reading</span>
          <span>Last seen</span>
          <span>Status</span>
        </div>
        {rows.map((row) => (
          <div key={row.node} className="sensor-row">
            <span className="sensor-id">{row.node}</span>
            <span>{row.type}</span>
            <span className="sensor-mono">{row.detail}</span>
            <span className="sensor-mono">{timeAgoLabel(row.lastSeen)}</span>
            <span className={`sensor-status sensor-status-${row.status}`}>
              <span className="sensor-status-dot" />
              {row.status === "online" ? "Online" : "Offline"}
            </span>
          </div>
        ))}
      </div>

      <p className="sensor-ble-note">
        BLE anchor status comes directly from its latest signal window and becomes offline after the configured timeout.
      </p>
    </div>
  );
}
