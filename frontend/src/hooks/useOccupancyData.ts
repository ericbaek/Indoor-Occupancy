import { useEffect, useRef, useState } from "react";
import type {
  RadarTarget,
  OccupancyStatus,
  OccupancyEvent,
  OccupancyPoint,
  RadarDevice,
} from "../data";

// Point this at your Flask backend. Override with a Vite env var
// (VITE_API_BASE_URL in a .env file) if the backend runs somewhere else.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:5000/api";

const POLL_MS = 3000;

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
  /** Occupancy trend built from real events (running total over time), for OccupancyChart. */
  occupancySeries: OccupancyPoint[];
  lastOccupancyEventAt: string | null;
  lastRadarUpdateAt: string | null;
  lastUpdated: Date;
  isLive: boolean;
  error: string | null;
};

const initialState: OccupancyData = {
  occupancy: 0,
  status: null,
  radarPresence: false,
  radarTargetCount: 0,
  radarTargets: [],
  events: [],
  occupancySeries: [],
  lastOccupancyEventAt: null,
  lastRadarUpdateAt: null,
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

function buildOccupancySeries(events: OccupancyEvent[]): OccupancyPoint[] {
  // `events` comes back newest-first from the backend; reverse to chronological
  // order and build a running total so the chart reflects real entry/exit history.
  const chronological = [...events].reverse();
  let running = 0;
  return chronological.map((e) => {
    running = Math.max(0, running + e.count_change);
    return { t: formatTimeLabel(e.received_at), count: running };
  });
}

/**
 * Single source of truth for live occupancy/radar data, polled from the
 * real Flask backend. Rooms, sensor nodes (CO2/battery), and alerts are
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
          fetch(`${API_BASE}/occupancy/events?limit=50`),
        ]);

        if (!statusRes.ok) throw new Error(`occupancy/status: ${statusRes.status}`);
        if (!radarRes.ok) throw new Error(`radar/latest: ${radarRes.status}`);
        if (!eventsRes.ok) throw new Error(`occupancy/events: ${eventsRes.status}`);

        const status: OccupancyStatus = await statusRes.json();
        const radarJson: { devices: RadarDevice[] } = await radarRes.json();
        const eventsJson: { events: OccupancyEvent[] } = await eventsRes.json();

        if (cancelledRef.current) return;

        setState({
          occupancy: status.occupancy,
          status: status.status,
          radarPresence: status.radar_presence,
          radarTargetCount: status.radar_target_count,
          radarTargets: mapRadarDevicesToTargets(radarJson.devices ?? []),
          events: eventsJson.events ?? [],
          occupancySeries: buildOccupancySeries(eventsJson.events ?? []),
          lastOccupancyEventAt: status.last_occupancy_event_at,
          lastRadarUpdateAt: status.last_radar_update_at,
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