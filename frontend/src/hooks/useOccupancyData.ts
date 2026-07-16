import { useEffect, useState } from "react";
import {
  radarTargets as mockRadarTargets,
  sensorNodes as mockSensorNodes,
  rooms as mockRooms,
  alerts as mockAlerts,
  occupancySeriesByRange as mockSeriesByRange,
  type RadarTarget,
  type SensorNode,
  type RoomState,
  type Alert,
  type OccupancyPoint,
  type OccupancyRange,
} from "../data";

export type OccupancyData = {
  radarTargets: RadarTarget[];
  sensorNodes: SensorNode[];
  rooms: RoomState[];
  alerts: Alert[];
  occupancySeriesByRange: Record<OccupancyRange, OccupancyPoint[]>;
  lastUpdated: Date;
  isLive: boolean;
};

const POLL_MS = 3000;

/**
 * Single source of truth for dashboard data.
 *
 * Right now this just re-emits the mock data on an interval so the UI
 * behaves like a live feed. Once the backend is ready, replace the body
 * of `fetchLatest()` with the real call (REST poll, or drop the
 * setInterval entirely and push updates from a WebSocket/MQTT
 * subscription instead) — nothing outside this hook needs to change.
 */
export function useOccupancyData(): OccupancyData {
  const [state, setState] = useState<OccupancyData>({
    radarTargets: mockRadarTargets,
    sensorNodes: mockSensorNodes,
    rooms: mockRooms,
    alerts: mockAlerts,
    occupancySeriesByRange: mockSeriesByRange,
    lastUpdated: new Date(),
    isLive: false,
  });

  useEffect(() => {
    let cancelled = false;

    async function fetchLatest() {
      // TODO(backend): replace with real fetch, e.g.
      //   const res = await fetch("/api/occupancy/latest");
      //   const json = await res.json();
      // and map `json` onto RadarTarget[] / SensorNode[] / RoomState[] / Alert[].
      const next: OccupancyData = {
        radarTargets: mockRadarTargets,
        sensorNodes: mockSensorNodes,
        rooms: mockRooms,
        alerts: mockAlerts,
        occupancySeriesByRange: mockSeriesByRange,
        lastUpdated: new Date(),
        isLive: true,
      };
      if (!cancelled) setState(next);
    }

    fetchLatest();
    const id = setInterval(fetchLatest, POLL_MS);
    return () => {
      cancelled = true;
      clearInterval(id);
    };
  }, []);

  return state;
}