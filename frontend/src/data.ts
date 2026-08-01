export type RadarTarget = {
  id: number;
  angle: number;
  distance: number;
  speed: number;
};

export type SensorNode = {
  id: string;
  room: string;
  pirOut: boolean;
  pirIn: boolean;
  mmwaveTargets: number;
  status: "online" | "offline";
};

export type RoomState = {
  room: string;
  occupancy: number;
  capacity: number;
  level: "safe" | "near-limit" | "over";
};

export type Alert = {
  id: string;
  kind: "capacity" | "offline";
  title: string;
  detail: string;
  time: string;
};

export type OccupancyPoint = { t: string; count: number };

export type Co2Point = { t: string; ppm: number };

export type OccupancyRange = "5m" | "10m" | "30m" | "1H" | "2H";

// ---------------------------------------------------------------------------
// Real backend types — these mirror the actual JSON shapes returned by the
// Flask API (see backend/app/routes.py). Unlike the mock types above, these
// are not fabricated — they exist because the backend genuinely provides
// this data (single doorway with PIR + mmWave radar and no room model yet).
// ---------------------------------------------------------------------------

export type BackendRadarTarget = {
  target_id: number;
  x_mm: number;
  y_mm: number;
  distance_mm: number;
  angle_deg: number;
  speed_cm_s: number;
};

export type RadarDevice = {
  device_id: string;
  uptime_ms: number;
  target_count: number;
  targets: BackendRadarTarget[];
  received_at: string;
};

export type OccupancyStatus = {
  occupancy: number;
  status: "confirmed" | "uncertain";
  radar_presence: boolean;
  radar_target_count: number;
  last_occupancy_event_at: string | null;
  last_radar_update_at: string | null;
  mismatch_started_at: string | null;
  // Environment / CO2 fields, surfaced on /api/occupancy/status alongside
  // the SCD41 sensor endpoints (/api/co2/latest, /api/co2/history/<id>).
  co2_ppm?: number | null;
  co2_level?: "normal" | "elevated" | "high" | string | null;
  temperature_c?: number | null;
  humidity_percent?: number | null;
  last_environment_update_at?: string | null;
  bluetooth_tag_count?: number;
  bluetooth_zones?: Record<string, number>;
  bluetooth_positions?: Array<{
    tag_id: string;
    x: number;
    y: number;
    label: string;
  }>;
};

export type BlePosition = {
  tag_id: string;
  status: "inside" | "outside" | "unknown";
  zone: string;
  stable_zone: string;
  position: {
    x: number;
    y: number;
    unit: string;
    method: string;
    label: string;
    quality: number;
  } | null;
  strongest_scanner: string | null;
  confidence_db: number;
  scanner_rssi: Record<string, number>;
  estimated_distances: Record<string, number>;
  last_seen_at: string;
};

export type Co2Reading = {
  id?: number;
  device_id: string;
  co2_ppm: number;
  temperature_c: number;
  humidity_percent: number;
  uptime_ms: number;
  received_at: string;
};

export type OccupancyEvent = {
  id: number;
  device_id: string;
  event_id: number;
  event: "entry" | "exit";
  count_change: number;
  duration_ms: number;
  uptime_ms: number;
  received_at: string;
};

// Live radar targets — shape matches the RD-03D UART frame the team is
// parsing in Thonny (angle / distance / speed per target, up to 3).
export const radarTargets: RadarTarget[] = [
  { id: 1, angle: -6.2, distance: 469.8, speed: 0 },
  { id: 2, angle: 0, distance: 0, speed: 0 },
  { id: 3, angle: 0, distance: 0, speed: 0 },
];

export const sensorNodes: SensorNode[] = [
  { id: "NODE-01", room: "K17-101", pirOut: true, pirIn: false, mmwaveTargets: 1, status: "online" },
  { id: "NODE-02", room: "K17-101", pirOut: false, pirIn: false, mmwaveTargets: 1, status: "online" },
  { id: "NODE-03", room: "K17-102", pirOut: true, pirIn: true, mmwaveTargets: 2, status: "online" },
  { id: "NODE-04", room: "K17-103", pirOut: true, pirIn: false, mmwaveTargets: 0, status: "offline" },
  { id: "NODE-05", room: "K17-104", pirOut: false, pirIn: false, mmwaveTargets: 0, status: "online" },
];

export const rooms: RoomState[] = [
  { room: "K17-101", occupancy: 24, capacity: 40, level: "safe" },
  { room: "K17-102", occupancy: 38, capacity: 40, level: "near-limit" },
  { room: "K17-103", occupancy: 44, capacity: 40, level: "over" },
  { room: "K17-104", occupancy: 12, capacity: 30, level: "safe" },
];

export const alerts: Alert[] = [
  { id: "a1", kind: "capacity", title: "Over capacity", detail: "K17-103 is over capacity (44/40)", time: "10:20 AM" },
  { id: "a3", kind: "offline", title: "Node offline", detail: "NODE-04 in K17-103 stopped reporting", time: "10:15 AM" },
];