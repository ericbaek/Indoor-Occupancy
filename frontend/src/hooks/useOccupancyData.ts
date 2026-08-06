import { useEffect, useRef, useState } from "react";
import type {
  RadarTarget,
  OccupancyStatus,
  OccupancyEvent,
  OccupancyPoint,
  RadarDevice,
  Co2Reading,
  Co2Point,
} from "../data";
import {
  appendOccupancyPoint,
  MAX_OCCUPANCY_HISTORY_MS,
  resolveOccupancyTimestamp,
} from "../lib/occupancyHistory";

// Vite proxies /api to Flask during native development.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "/api";

const DEFAULT_POLL_MS = 1000;

// Recent events still power the Sensors page's latest-event details. The
// occupancy chart uses status snapshots instead of reconstructing this list.
const EVENTS_FETCH_LIMIT = 500;

// The co2/history endpoint caps at 200 server-side; 100 is plenty to fill
// the chart without over-fetching every poll.
const CO2_HISTORY_LIMIT = 100;

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
  /** Successful live status readings from the last two hours, oldest first. */
  occupancySeries: OccupancyPoint[];
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
  /** CO2 device currently backing the status card, or null if none has reported. */
  co2DeviceId: string | null;
  /** Recent readings for co2DeviceId, oldest first, ready to plot. */
  co2History: Co2Point[];
  /** Raw per-device radar snapshots (device_id, received_at, target_count) \u2014 for Sensors page online/offline. */
  radarDevices: RadarDevice[];
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
  mismatchStartedAt: null,
  co2Ppm: null,
  co2Level: null,
  temperatureC: null,
  humidityPercent: null,
  lastEnvironmentUpdateAt: null,
  co2DeviceId: null,
  co2History: [],
  radarDevices: [],
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

function buildCo2Series(readingsNewestFirst: Co2Reading[]): Co2Point[] {
  return [...readingsNewestFirst]
    .reverse()
    .map((r) => ({ t: formatTimeLabel(r.received_at), ppm: r.co2_ppm }));
}

function pickHighestCo2Device(devices: Co2Reading[]): string | null {
  let best: Co2Reading | null = null;
  for (const d of devices) {
    if (best === null || d.co2_ppm > best.co2_ppm) best = d;
  }
  return best?.device_id ?? null;
}

/**
 * Single source of truth for live occupancy/radar data, polled from the
 * real Flask backend. Rooms, sensor nodes, and alerts are
 * NOT included here — the backend doesn't model those yet, so components
 * that need them still read the mock arrays directly from `../data`.
 */
export function useOccupancyData(pollMs: number = DEFAULT_POLL_MS): OccupancyData {
  const [state, setState] = useState<OccupancyData>(initialState);
  const requestSequenceRef = useRef(0);
  const appliedStatusRequestRef = useRef(0);
  const appliedAncillaryRequestRef = useRef(0);

  useEffect(() => {
    let disposed = false;
    const controllers = new Set<AbortController>();

    function isAborted(error: unknown, signal: AbortSignal): boolean {
      return signal.aborted || (error instanceof DOMException && error.name === "AbortError");
    }

    async function getJson<T>(url: string, signal: AbortSignal): Promise<T> {
      const response = await fetch(url, { signal });
      if (!response.ok) throw new Error(`${url}: ${response.status}`);
      return response.json() as Promise<T>;
    }

    async function updateOccupancyStatus(requestId: number, signal: AbortSignal) {
      try {
        const status = await getJson<OccupancyStatus>(`${API_BASE}/occupancy/status`, signal);
        const receivedAt = Date.now();
        if (!Number.isFinite(status.occupancy)) {
          throw new Error("occupancy/status: invalid occupancy value");
        }
        const resolvedTimestamp = resolveOccupancyTimestamp(status, receivedAt);
        if (resolvedTimestamp < receivedAt - MAX_OCCUPANCY_HISTORY_MS) {
          throw new Error("occupancy/status: stale reading timestamp");
        }
        // A future server clock cannot produce a visible point on an axis ending now.
        const timestamp = Math.min(resolvedTimestamp, receivedAt);
        if (
          disposed ||
          signal.aborted ||
          requestId < appliedStatusRequestRef.current
        ) return;

        appliedStatusRequestRef.current = requestId;

        setState((previous) => {
          const latestTimestamp = previous.occupancySeries.at(-1)?.timestamp;
          if (latestTimestamp !== undefined && timestamp < latestTimestamp) {
            return previous;
          }

          return {
            ...previous,
            occupancy: status.occupancy,
            status: status.status,
            radarPresence: status.radar_presence,
            radarTargetCount: status.radar_target_count,
            occupancySeries: appendOccupancyPoint(
              previous.occupancySeries,
              { timestamp, count: status.occupancy },
              receivedAt,
            ),
            lastOccupancyEventAt: status.last_occupancy_event_at,
            lastRadarUpdateAt: status.last_radar_update_at,
            mismatchStartedAt: status.mismatch_started_at,
            co2Ppm: status.co2_ppm ?? null,
            co2Level: status.co2_level ?? null,
            temperatureC: status.temperature_c ?? null,
            humidityPercent: status.humidity_percent ?? null,
            lastEnvironmentUpdateAt: status.last_environment_update_at ?? null,
            lastUpdated: new Date(receivedAt),
            isLive: true,
            error: null,
          };
        });
      } catch (err) {
        if (disposed || isAborted(err, signal)) return;
        if (requestId < appliedStatusRequestRef.current) return;
        setState((prev) => ({
          ...prev,
          isLive: false,
          error: err instanceof Error ? err.message : "Failed to fetch occupancy data",
        }));
        console.error("useOccupancyData: fetch failed", err);
      }
    }

    async function fetchCo2Data(signal: AbortSignal) {
      const latest = await getJson<{ devices: Co2Reading[] }>(`${API_BASE}/co2/latest`, signal);
      const co2DeviceId = pickHighestCo2Device(latest.devices ?? []);
      if (!co2DeviceId) return { co2DeviceId: null, co2History: [] as Co2Point[] };

      const history = await getJson<{ readings: Co2Reading[] }>(
        `${API_BASE}/co2/history/${encodeURIComponent(co2DeviceId)}?limit=${CO2_HISTORY_LIMIT}`,
        signal,
      );
      return {
        co2DeviceId,
        co2History: buildCo2Series(history.readings ?? []),
      };
    }

    async function updateAncillaryData(requestId: number, signal: AbortSignal) {
      const [radar, events, co2] = await Promise.allSettled([
        getJson<{ devices: RadarDevice[] }>(`${API_BASE}/radar/latest`, signal),
        getJson<{ events: OccupancyEvent[] }>(
          `${API_BASE}/occupancy/events?limit=${EVENTS_FETCH_LIMIT}`,
          signal,
        ),
        fetchCo2Data(signal),
      ]);

      if (
        disposed ||
        signal.aborted ||
        requestId < appliedAncillaryRequestRef.current
      ) return;

      appliedAncillaryRequestRef.current = requestId;
      setState((previous) => ({
        ...previous,
        radarTargets:
          radar.status === "fulfilled"
            ? mapRadarDevicesToTargets(radar.value.devices ?? [])
            : previous.radarTargets,
        radarDevices:
          radar.status === "fulfilled"
            ? radar.value.devices ?? []
            : previous.radarDevices,
        events:
          events.status === "fulfilled"
            ? events.value.events ?? []
            : previous.events,
        co2DeviceId:
          co2.status === "fulfilled"
            ? co2.value.co2DeviceId
            : previous.co2DeviceId,
        co2History:
          co2.status === "fulfilled"
            ? co2.value.co2History
            : previous.co2History,
      }));
    }

    async function fetchLatest() {
      const requestId = ++requestSequenceRef.current;
      const controller = new AbortController();
      controllers.add(controller);

      try {
        await Promise.all([
          updateOccupancyStatus(requestId, controller.signal),
          updateAncillaryData(requestId, controller.signal),
        ]);
      } finally {
        controllers.delete(controller);
      }
    }

    fetchLatest();
    const id = setInterval(fetchLatest, pollMs);
    return () => {
      disposed = true;
      clearInterval(id);
      controllers.forEach((controller) => controller.abort());
      controllers.clear();
    };
  }, [pollMs]);

  return state;
}
