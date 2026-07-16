import { useEffect, useRef, useState } from "react";
import type {
  RadarTarget,
  OccupancyStatus,
  OccupancyEvent,
  OccupancyPoint,
  OccupancyRange,
  RadarDevice,
} from "../data";

// Point this at your Flask backend. Override with a Vite env var
// (VITE_API_BASE_URL in a .env file) if the backend runs somewhere else.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

const POLL_MS = 3000;

// How far back each range looks, and how many points to plot across that
// window. Bucketing (rather than plotting raw events) keeps 1W/1M readable
// once there's more than a handful of entries, and gives every range a
// value even in the gaps between real events.
const RANGE_CONFIG: Record<OccupancyRange, { windowMs: number; buckets: number; label: (d: Date) => string }> = {
  "1H": {
    windowMs: 60 * 60 * 1000,
    buckets: 12,
    label: (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  },
  "6H": {
    windowMs: 6 * 60 * 60 * 1000,
    buckets: 12,
    label: (d) => d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
  },
  "1D": {
    windowMs: 24 * 60 * 60 * 1000,
    buckets: 12,
    label: (d) => d.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" }),
  },
  "1W": {
    windowMs: 7 * 24 * 60 * 60 * 1000,
    buckets: 7,
    label: (d) => d.toLocaleDateString([], { weekday: "short" }),
  },
  "1M": {
    windowMs: 30 * 24 * 60 * 60 * 1000,
    buckets: 10,
    label: (d) => d.toLocaleDateString([], { day: "2-digit", month: "short" }),
  },
};

// Fetch enough history to have a shot at filling the 1M window. The backend
// only supports a flat `limit`, not a time-range filter, so we over-fetch
// and bucket client-side.
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
  /** Occupancy trend built from real events (running total, one point per event), for the "1D" tab. */
  occupancySeries: OccupancyPoint[];
  /** Same real event history, bucketed per range window — powers all 5 chart tabs. */
  occupancySeriesByRange: Record<OccupancyRange, OccupancyPoint[]>;
  lastOccupancyEventAt: string | null;
  lastRadarUpdateAt: string | null;
  /** When the current PIR/radar mismatch began, or null if none is active. */
  mismatchStartedAt: string | null;
  lastUpdated: Date;
  isLive: boolean;
  error: string | null;
};

const EMPTY_RANGES: Record<OccupancyRange, OccupancyPoint[]> = {
  "1H": [], "6H": [], "1D": [], "1W": [], "1M": [],
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
        const [statusRes, radarRes, eventsRes] = await Promise.all([
          fetch(`${API_BASE}/occupancy/status`),
          fetch(`${API_BASE}/radar/latest`),
          fetch(`${API_BASE}/occupancy/events?limit=${EVENTS_FETCH_LIMIT}`),
        ]);

        if (!statusRes.ok) throw new Error(`occupancy/status: ${statusRes.status}`);
        if (!radarRes.ok) throw new Error(`radar/latest: ${radarRes.status}`);
        if (!eventsRes.ok) throw new Error(`occupancy/events: ${eventsRes.status}`);

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
