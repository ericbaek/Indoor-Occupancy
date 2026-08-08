import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type {
  BleSignalSummary,
  OccupancyEvent,
  OccupancyStatus,
  RadarDevice,
} from "../data";
import { useOccupancyData } from "./useOccupancyData";

const NOW = Date.parse("2026-08-03T12:00:00.000Z");

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

const status: OccupancyStatus = {
  occupancy: 3,
  status: "confirmed",
  radar_presence: true,
  radar_target_count: 1,
  last_occupancy_event_at: "2026-08-03T11:59:30.000Z",
  last_radar_update_at: "2026-08-03T11:59:59.000Z",
  mismatch_started_at: null,
  co2_ppm: 820,
  co2_level: "elevated",
  temperature_c: 22.4,
  humidity_percent: 48.2,
  last_environment_update_at: "2026-08-03T11:59:55.000Z",
};

const eventsNewestFirst: OccupancyEvent[] = [
  {
    id: 2,
    device_id: "doorway-pico-01",
    event_id: 2,
    event: "exit",
    count_change: -1,
    duration_ms: 500,
    uptime_ms: 2000,
    received_at: "2026-08-03T11:59:30.000Z",
  },
  {
    id: 1,
    device_id: "doorway-pico-01",
    event_id: 1,
    event: "entry",
    count_change: 1,
    duration_ms: 450,
    uptime_ms: 1000,
    received_at: "2026-08-03T11:58:30.000Z",
  },
];

const radarDevice: RadarDevice = {
  device_id: "doorway-pico-01",
  uptime_ms: 3000,
  target_count: 1,
  received_at: "2026-08-03T11:59:59.000Z",
  targets: [
    {
      target_id: 1,
      x_mm: 100,
      y_mm: 900,
      distance_mm: 906,
      angle_deg: 6.3,
      speed_cm_s: 4,
    },
  ],
};

const bleSignal: BleSignalSummary = {
  measurement: "relative_bluetooth_signal_intensity",
  stronger_zone: "left",
  anchor_timeout_seconds: 15,
  ema_alpha: 0.3,
  zones: {
    left: {
      anchor_id: "left-anchor",
      zone: "left",
      status: "active",
      average_rssi: -50,
      signal_score: 83,
      last_seen_at: "2026-08-03T11:59:59.000Z",
      calibration_offset_db: 0,
    },
    right: {
      anchor_id: "right-anchor",
      zone: "right",
      status: "active",
      average_rssi: -65,
      signal_score: 58,
      last_seen_at: "2026-08-03T11:59:59.000Z",
      calibration_offset_db: 0,
    },
  },
};

function installFetchMock(statusCode = 200) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/occupancy/status")) return jsonResponse(status, statusCode);
    if (url.endsWith("/radar/latest")) return jsonResponse({ devices: [radarDevice] });
    if (url.includes("/occupancy/events")) return jsonResponse({ events: eventsNewestFirst });
    if (url.endsWith("/bluetooth/signal-strength")) return jsonResponse(bleSignal);
    if (url.endsWith("/co2/latest")) return jsonResponse({ devices: [] });
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

async function flushRequests() {
  await act(async () => {
    await Promise.resolve();
    await Promise.resolve();
    await Promise.resolve();
  });
}

describe("useOccupancyData", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("maps live sensor data and anchors the event series to current occupancy", async () => {
    installFetchMock();
    const { result } = renderHook(() => useOccupancyData(1000));
    await flushRequests();

    expect(result.current.isLive).toBe(true);
    expect(result.current.occupancy).toBe(3);
    expect(result.current.radarTargets).toEqual([
      { id: 1, angle: 6.3, distance: 906, speed: 4 },
    ]);
    expect(result.current.occupancySeries.map((point) => point.count)).toEqual([4, 3]);
    expect(result.current.bleSignal?.stronger_zone).toBe("left");
    expect(result.current.co2Ppm).toBe(820);
  });

  it("keeps the previous state when a later poll fails", async () => {
    let fail = false;
    const fetchMock = installFetchMock();
    fetchMock.mockImplementation(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (fail && url.endsWith("/occupancy/status")) return jsonResponse({}, 503);
      if (url.endsWith("/occupancy/status")) return jsonResponse(status);
      if (url.endsWith("/radar/latest")) return jsonResponse({ devices: [radarDevice] });
      if (url.includes("/occupancy/events")) return jsonResponse({ events: eventsNewestFirst });
      if (url.endsWith("/bluetooth/signal-strength")) return jsonResponse(bleSignal);
      if (url.endsWith("/co2/latest")) return jsonResponse({ devices: [] });
      throw new Error(`Unexpected request: ${url}`);
    });

    const { result } = renderHook(() => useOccupancyData(1000));
    await flushRequests();
    fail = true;
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1000);
    });

    expect(result.current.occupancy).toBe(3);
    expect(result.current.isLive).toBe(false);
    expect(result.current.error).toContain("occupancy/status: 503");
  });

  it("stops polling after unmount", () => {
    installFetchMock();
    const { unmount } = renderHook(() => useOccupancyData(1000));
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });
});
