export type RadarTarget = {
  id: number;
  angle: number;
  distance: number;
  speed: number;
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
// ---------------------------------------------------------------------------
// Reports — mock, pending backend historical-query support.
//
// Nothing under backend/app/ computes MAE/RMSE/fusion-gain or stores
// exportable summaries yet (confirmed: no "evaluation"/"fusion" logic in
// routes.py, occupancy.py, or database.py as of this build). This section
// is shaped to match what the backend WOULD need to return so the frontend
// can be swapped from mock to live with no component changes — see the
// contract notes below each type. Remove this comment block once
// /api/reports/* exists and fetch() replaces these constants in Reports.tsx.
// ---------------------------------------------------------------------------

/** One row of the fusion evaluation table (per sensing modality / model). */
export type EvaluationMetric = {
  /** Human label shown in the table, e.g. "PIR + mmWave fusion". */
  model: string;
  /** Mean Absolute Error in occupancy count vs. ground truth (manual count / video review). */
  mae: number;
  /** Root Mean Squared Error, same units as MAE — penalises large misses more. */
  rmse: number;
  /**
   * Fusion gain: % reduction in MAE vs. the single-sensor baseline
   * (PIR-only). Positive = fusion helped. Null for the baseline row itself.
   */
  fusionGainPercent: number | null;
  /** Number of ground-truth samples the metric was computed over. */
  sampleCount: number;
};

/** Top-line summary stats shown as StatCards at the top of Reports. */
export type ReportSummary = {
  rangeLabel: string;
  totalHoursTracked: number;
  avgOccupancy: number;
  peakOccupancy: number;
  peakAt: string;
  /** % of expected sensor readings actually received in this range. */
  dataCompletenessPercent: number;
};

/** One exportable historical report file. */
export type ReportExport = {
  id: string;
  name: string;
  room: string;
  rangeLabel: string;
  format: "csv" | "pdf";
  generatedAt: string;
  sizeKb: number;
};

export const reportSummary: ReportSummary = {
  rangeLabel: "Last 7 days",
  totalHoursTracked: 58.4,
  avgOccupancy: 3.2,
  peakOccupancy: 9,
  peakAt: "Wed 12:40 PM",
  dataCompletenessPercent: 91,
};

export const evaluationMetrics: EvaluationMetric[] = [
  { model: "PIR only (baseline)", mae: 1.84, rmse: 2.31, fusionGainPercent: null, sampleCount: 420 },
  { model: "mmWave only", mae: 1.12, rmse: 1.55, fusionGainPercent: 39.1, sampleCount: 420 },
  { model: "PIR + mmWave fusion", mae: 0.67, rmse: 0.98, fusionGainPercent: 63.6, sampleCount: 420 },
  { model: "PIR + mmWave + BLE zone", mae: 0.58, rmse: 0.89, fusionGainPercent: 68.5, sampleCount: 310 },
];

export const reportExports: ReportExport[] = [
  { id: "r1", name: "Weekly occupancy summary", room: "K17-101 (doorway)", rangeLabel: "Jul 21 – Jul 27", format: "csv", generatedAt: "2026-07-28T09:02:00+10:00", sizeKb: 48 },
  { id: "r2", name: "Fusion evaluation report", room: "K17-101 (doorway)", rangeLabel: "Jul 21 – Jul 27", format: "pdf", generatedAt: "2026-07-28T09:02:00+10:00", sizeKb: 612 },
  { id: "r3", name: "CO2 trend export", room: "K17-101 (doorway)", rangeLabel: "Jul 14 – Jul 20", format: "csv", generatedAt: "2026-07-21T08:55:00+10:00", sizeKb: 31 },
];
