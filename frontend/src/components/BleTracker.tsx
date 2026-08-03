import "./BleTracker.css";
import type { BleDeviceState, BleZoneName } from "../data";

interface BleTrackerProps {
  deviceCount: number;
  zones: Record<BleZoneName, number>;
  devices: BleDeviceState[];
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

function formatRssi(device: BleDeviceState, zone: BleZoneName): string {
  const rssi = device.scanner_rssi[`anchor-${zone}`];
  return rssi === undefined ? "--" : `${rssi.toFixed(1)} dBm`;
}

export default function BleTracker({ deviceCount, zones, devices }: BleTrackerProps) {
  const unassigned = devices.filter((device) => device.current_zone === "unknown");

  return (
    <section className="ble-tracker-card card-base" aria-label="Bluetooth room heatmap">
      <div className="ble-header">
        <div>
          <h3 className="card-title">Bluetooth Device Distribution</h3>
          <p className="ble-subtitle">Up to 5 real devices · smoothed two-anchor RSSI</p>
        </div>
        <span className={`ble-badge ${deviceCount > 0 ? "active" : "inactive"}`}>
          {deviceCount} active device{deviceCount === 1 ? "" : "s"}
        </span>
      </div>

      <div className="ble-heatmap">
        {ZONE_DETAILS.map((zone) => {
          const count = zones[zone.id] ?? 0;
          const zoneDevices = devices.filter((device) => device.current_zone === zone.id);
          return (
            <article
              key={zone.id}
              className={`ble-zone ble-zone-${intensity(count)}`}
              aria-label={`${zone.label}: ${count} devices`}
            >
              <span className="ble-zone-label">{zone.label}</span>
              <strong className="ble-zone-count">{count}</strong>
              <span className="ble-zone-unit">device{count === 1 ? "" : "s"}</span>
              <span className="ble-zone-anchor">{zone.anchor}</span>

              <div className="ble-zone-tags">
                {zoneDevices.map((device) => (
                  <span className="ble-tag-chip" key={device.device_id}>
                    <span>{device.device_name}</span>
                    <span>{formatRssi(device, zone.id)}</span>
                  </span>
                ))}
              </div>
            </article>
          );
        })}
      </div>

      {unassigned.length > 0 && (
        <p className="ble-unassigned">
          Waiting for both anchors: {unassigned.map((device) => device.device_name).join(", ")}
        </p>
      )}
      <p className="ble-note">
        Devices time out after 5 seconds. The opposite anchor must become at least 5 dBm stronger to switch sides.
      </p>
    </section>
  );
}
