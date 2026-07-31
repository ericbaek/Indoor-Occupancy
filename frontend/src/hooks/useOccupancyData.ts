import { useEffect, useRef, useState } from "react";
import type {
  RadarTarget,
  OccupancyStatus,
  OccupancyEvent,
  OccupancyPoint,
  OccupancyRange,
  RadarDevice,
  BlePosition,
} from "../data";

// Point this at your Flask backend. Override with a Vite env var
// (VITE_API_BASE_URL in a .env file) if the backend runs somewhere else.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

const POLL_MS = 1000;

// How far back each range looks, and how many points to plot across that
// window. Bucketing (rather than plotting raw events) smooths the line even
// with just a handful of entries, and gives every range a value even in the
// gaps between real events.
const RANGE_CONFIG: Record<OccupancyRange, { windowMs: number; buckets: number; label: (d: Date) => string }> = {
  "5m": {
    windowMs: 5 * 60 * 1000,
    buckets: 10, // 30s per bucket
    label: (d) => d.toLocaleTimeString([], { minute: "2-digit", second: "2-digit" }),
  },
  "10m": {
    windowMs: 10 * 60 * 1000,
    buckets: 10, // 1min per bucket
    label: (d) => d.toLocaleTimeString([], { minute: "2-digit", second: "2-digit" }),
  },
  "30m": {
    windowMs: 30 * 60 * 1000,
    buckets: 15, // 2min per bucket
    label: (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  },
  "1H": {
    windowMs: 60 * 60 * 1000,
    buckets: 12, // 5min per bucket
    label: (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  },
  "2H": {
    windowMs: 2 * 60 * 60 * 1000,
    buckets: 12, // 10min per bucket
    label: (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  },
};

// Fetch enough history to comfortably fill the widest window (2H) with
// real events. The backend only supports a flat `limit`, not a time-range
// filter, so we over-fetch and bucket client-side.
const EVENTS_FETCH_LIMIT = 500;

export type OccupancyData = {
  /** Current occupancy count (sum of entry/exit events, clamped >= 0). */
  occupancy: number;
  /** "confirmed" = PIR count and radar presence agree. "uncertain" = they don't (yet). */
  status: OccupancyStatus["status"] | null;
  radarPresence: boolean;
  radarTargetCount: number;
  /** Live radar targets, mapped into the shape RadarScope expects. */
  radarTargets: RadarTarget[];
  /** Recent entry/exit events, newest first, straight from the backend. */
  events: OccupancyEvent[];
  /** Occupancy trend built from real events (running total, one point per event), raw/unbucketed. */
  occupancySeries: OccupancyPoint[];
  /** Same real event history, bucketed per range window — powers all 5 chart tabs (5m/10m/30m/1H/2H). */
  occupancySeriesByRange: Record<OccupancyRange, OccupancyPoint[]>;
  lastOccupancyEventAt: string | null;
  lastRadarUpdateAt: string | null;
  /** When the current PIR/radar mismatch began, or null if none is active. */
  mismatchStartedAt: string | null;
  /** Latest CO2 ppm reading from the SCD41 sensor, or null if none yet. */
  co2Ppm: number | null;
  /** Backend-classified level for the current co2Ppm ("low" | "moderate" | "high"). */
  co2Level: string | null;
  temperatureC: number | null;
  humidityPercent: number | null;
  lastEnvironmentUpdateAt: string | null;
  bleTagCount: number;
  bleZones: Record<string, number>;
  blePositions: Array<{tag_id: string; x: number; y: number; label: string}>;
  bleTagsFull: BlePosition[];
  lastUpdated: Date;
  isLive: boolean;
  error: string | null;
};

const EMPTY_RANGES: Record<OccupancyRange, OccupancyPoint[]> = {
  "5m": [], "10m": [], "30m": [], "1H": [], "2H": [],
};

const initialState: OccupancyData = {
  occupancy: 0,
  status: null,
  radarPresence: false,
  radarTargetCount: 0,
  radarTargets: [],
  events: [],
  occupancySeries: [],
  occupancySeriesByRange: EMPTY_RANGES,
  lastOccupancyEventAt: null,
  lastRadarUpdateAt: null,
  mismatchStartedAt: null,
  co2Ppm: null,
  co2Level: null,
  temperatureC: null,
  humidityPercent: null,
  lastEnvironmentUpdateAt: null,
  bleTagCount: 0,
  bleZones: {},
  blePositions: [],
  bleTagsFull: [],
  lastUpdated: new Date(),
  isLive: false,
  error: null,
};

function mapRadarDevicesToTargets(devices: RadarDevice[]): RadarTarget[] {
  // Flatten targets across all devices into the flat shape RadarScope renders.
  return devices.flatMap((device) =>
    device.targets.map((t) => ({
      id: t.target_id,
      angle: t.angle_deg,
      distance: t.distance_mm,
      speed: t.speed_cm_s,
    }))
  );
}

function formatTimeLabel(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" });
}

function buildOccupancySeries(eventsChronological: OccupancyEvent[]): OccupancyPoint[] {
  let running = 0;
  return eventsChronological.map((e) => {
    running = Math.max(0, running + e.count_change);
    return { t: formatTimeLabel(e.received_at), count: running };
  });
}

type CumPoint = { ts: number; value: number };

function buildCumulative(eventsChronological: OccupancyEvent[]): CumPoint[] {
  let running = 0;
  return eventsChronological.map((e) => {
    running = Math.max(0, running + e.count_change);
    return { ts: new Date(e.received_at).getTime(), value: running };
  });
}

/** Occupancy at time `t`, i.e. the value of the last event at or before `t` (0 if none yet). */
function valueAt(cumAsc: CumPoint[], t: number): number {
  let val = 0;
  for (const p of cumAsc) {
    if (p.ts > t) break;
    val = p.value;
  }
  return val;
}

function buildRangeSeries(cumAsc: CumPoint[], range: OccupancyRange): OccupancyPoint[] {
  const { windowMs, buckets, label } = RANGE_CONFIG[range];
  const now = Date.now();
  const start = now - windowMs;
  const step = windowMs / buckets;

  const points: OccupancyPoint[] = [];
  for (let i = 0; i <= buckets; i++) {
    const t = start + step * i;
    points.push({ t: label(new Date(t)), count: valueAt(cumAsc, t) });
  }
  return points;
}

function buildAllRangeSeries(eventsChronological: OccupancyEvent[]): Record<OccupancyRange, OccupancyPoint[]> {
  const cumAsc = buildCumulative(eventsChronological);
  const out = {} as Record<OccupancyRange, OccupancyPoint[]>;
  (Object.keys(RANGE_CONFIG) as OccupancyRange[]).forEach((range) => {
    out[range] = buildRangeSeries(cumAsc, range);
  });
  return out;
}

/**
 * Single source of truth for live occupancy/radar data, polled from the
 * real Flask backend. Rooms, sensor nodes, and alerts are
 * NOT included here — the backend doesn't model those yet, so components
 * that need them still read the mock arrays directly from `../data`.
 */
export function useOccupancyData(): OccupancyData {
  const [state, setState] = useState<OccupancyData>(initialState);
  const cancelledRef = useRef(false);

  useEffect(() => {
    cancelledRef.current = false;

    async function fetchLatest() {
      try {
        const [statusRes, radarRes, eventsRes, bleTagsRes] = await Promise.all([
          fetch(`${API_BASE}/occupancy/status`),
          fetch(`${API_BASE}/radar/latest`),
          fetch(`${API_BASE}/occupancy/events?limit=${EVENTS_FETCH_LIMIT}`),
          fetch(`${API_BASE}/bluetooth/tags`),
        ]);

        if (!statusRes.ok) throw new Error(`occupancy/status: ${statusRes.status}`);
        if (!radarRes.ok) throw new Error(`radar/latest: ${radarRes.status}`);
        if (!eventsRes.ok) throw new Error(`occupancy/events: ${eventsRes.status}`);
        // don't fail if BLE is down, just log
        let bleTagsFull: BlePosition[] = [];
        if (bleTagsRes.ok) {
           const bleJson = await bleTagsRes.json();
           bleTagsFull = bleJson.tags || [];
        }

        const status: OccupancyStatus = await statusRes.json();
        const radarJson: { devices: RadarDevice[] } = await radarRes.json();
        const eventsJson: { events: OccupancyEvent[] } = await eventsRes.json();

        if (cancelledRef.current) return;

        // Backend returns newest-first; flip to chronological once, reuse everywhere.
        const chronological = [...(eventsJson.events ?? [])].reverse();

        setState({
          occupancy: status.occupancy,
          status: status.status,
          radarPresence: status.radar_presence,
          radarTargetCount: status.radar_target_count,
          radarTargets: mapRadarDevicesToTargets(radarJson.devices ?? []),
          events: eventsJson.events ?? [],
          occupancySeries: buildOccupancySeries(chronological),
          occupancySeriesByRange: buildAllRangeSeries(chronological),
          lastOccupancyEventAt: status.last_occupancy_event_at,
          lastRadarUpdateAt: status.last_radar_update_at,
          mismatchStartedAt: status.mismatch_started_at,
          co2Ppm: status.co2_ppm ?? null,
          co2Level: status.co2_level ?? null,
          temperatureC: status.temperature_c ?? null,
          humidityPercent: status.humidity_percent ?? null,
          lastEnvironmentUpdateAt: status.last_environment_update_at ?? null,
          bleTagCount: status.bluetooth_tag_count ?? 0,
          bleZones: status.bluetooth_zones ?? {},
          blePositions: status.bluetooth_positions ?? [],
          bleTagsFull,
          lastUpdated: new Date(),
          isLive: true,
          error: null,
        });
      } catch (err) {
        if (cancelledRef.current) return;
        setState((prev) => ({
          ...prev,
          isLive: false,
          error: err instanceof Error ? err.message : "Failed to fetch occupancy data",
        }));
        console.error("useOccupancyData: fetch failed", err);
      }
    }

    fetchLatest();
    const id = setInterval(fetchLatest, POLL_MS);
    return () => {
      cancelledRef.current = true;
      clearInterval(id);
    };
  }, []);

  return state;
}