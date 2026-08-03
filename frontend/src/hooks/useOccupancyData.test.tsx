import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OccupancyStatus } from "../data";
import { MAX_OCCUPANCY_HISTORY_MS } from "../lib/occupancyHistory";
import { useOccupancyData } from "./useOccupancyData";

const START_TIME = Date.parse("2026-08-03T12:00:00.000Z");

function jsonResponse(body: unknown, status = 200): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  } as Response;
}

function statusReading(occupancy: number): OccupancyStatus {
  return {
    occupancy,
    status: "confirmed",
    radar_presence: true,
    radar_target_count: 3,
    last_occupancy_event_at: null,
    last_radar_update_at: null,
    mismatch_started_at: null,
  };
}

function installFetchMock(occupancies: number[]) {
  let statusIndex = 0;
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.endsWith("/occupancy/status")) {
      const occupancy = occupancies[Math.min(statusIndex, occupancies.length - 1)];
      statusIndex += 1;
      return jsonResponse(statusReading(occupancy));
    }
    if (url.endsWith("/radar/latest")) return jsonResponse({ devices: [] });
    if (url.includes("/occupancy/events")) return jsonResponse({ events: [] });
    if (url.endsWith("/bluetooth/tags")) return jsonResponse({ tags: [] });
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

function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => {
    resolve = done;
  });
  return { promise, resolve };
}

describe("useOccupancyData live history", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(START_TIME);
    vi.spyOn(console, "error").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
    vi.useRealTimers();
  });

  it("records ten one-second polling updates approximately one second apart", async () => {
    installFetchMock([1, 2, 3, 4, 5, 6, 7, 8, 9, 10]);
    const { result } = renderHook(() => useOccupancyData(1_000));
    await flushRequests();

    for (let index = 1; index < 10; index += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_000);
      });
    }

    expect(result.current.occupancySeries).toHaveLength(10);
    const timestamps = result.current.occupancySeries.map((point) => point.timestamp);
    expect(timestamps.slice(1).map((time, index) => time - timestamps[index])).toEqual(
      Array(9).fill(1_000),
    );
  });

  it("keeps the latest graph value equal to the current occupancy card value", async () => {
    installFetchMock([1, 4, 2]);
    const { result } = renderHook(() => useOccupancyData(1_000));
    await flushRequests();

    expect(result.current.occupancySeries.at(-1)?.count).toBe(result.current.occupancy);
    for (let index = 1; index < 3; index += 1) {
      await act(async () => {
        await vi.advanceTimersByTimeAsync(1_000);
      });
      expect(result.current.occupancySeries.at(-1)?.count).toBe(result.current.occupancy);
    }
    expect(result.current.occupancySeries.map((point) => point.count)).toEqual([1, 4, 2]);
  });

  it("never adds radar targets, random values, or failed readings to occupancy history", async () => {
    let statusCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/occupancy/status")) {
        statusCalls += 1;
        return statusCalls === 1
          ? jsonResponse(statusReading(7))
          : jsonResponse({ error: "offline" }, 503);
      }
      if (url.endsWith("/radar/latest")) {
        return jsonResponse({ devices: [{ target_count: 3, targets: [] }] });
      }
      if (url.includes("/occupancy/events")) return jsonResponse({ events: [] });
      if (url.endsWith("/bluetooth/tags")) return jsonResponse({ tags: [] });
      if (url.endsWith("/co2/latest")) return jsonResponse({ devices: [] });
      throw new Error(`Unexpected request: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useOccupancyData(1_000));
    await flushRequests();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(result.current.occupancy).toBe(7);
    expect(result.current.occupancySeries).toEqual([
      { timestamp: START_TIME, count: 7 },
    ]);
  });

  it("ignores an older response that resolves after a newer reading", async () => {
    const statusRequests = [deferred<Response>(), deferred<Response>()];
    let statusIndex = 0;
    vi.stubGlobal("fetch", vi.fn((input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/occupancy/status")) {
        const request = statusRequests[statusIndex];
        statusIndex += 1;
        return request.promise;
      }
      if (url.endsWith("/radar/latest")) return Promise.resolve(jsonResponse({ devices: [] }));
      if (url.includes("/occupancy/events")) return Promise.resolve(jsonResponse({ events: [] }));
      if (url.endsWith("/bluetooth/tags")) return Promise.resolve(jsonResponse({ tags: [] }));
      if (url.endsWith("/co2/latest")) return Promise.resolve(jsonResponse({ devices: [] }));
      return Promise.reject(new Error(`Unexpected request: ${url}`));
    }));

    const { result } = renderHook(() => useOccupancyData(1_000));
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    await act(async () => {
      statusRequests[1].resolve(jsonResponse(statusReading(2)));
      await Promise.resolve();
      await Promise.resolve();
    });
    await act(async () => {
      statusRequests[0].resolve(jsonResponse(statusReading(1)));
      await Promise.resolve();
      await Promise.resolve();
    });

    expect(result.current.occupancy).toBe(2);
    expect(result.current.occupancySeries.map((point) => point.count)).toEqual([2]);
  });

  it("ignores a newer poll carrying an older API reading timestamp", async () => {
    let statusCalls = 0;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/occupancy/status")) {
        statusCalls += 1;
        const reading = statusReading(statusCalls === 1 ? 2 : 9);
        reading.timestamp = new Date(
          statusCalls === 1 ? START_TIME : START_TIME - 1_000,
        ).toISOString();
        return jsonResponse(reading);
      }
      if (url.endsWith("/radar/latest")) return jsonResponse({ devices: [] });
      if (url.includes("/occupancy/events")) return jsonResponse({ events: [] });
      if (url.endsWith("/bluetooth/tags")) return jsonResponse({ tags: [] });
      if (url.endsWith("/co2/latest")) return jsonResponse({ devices: [] });
      throw new Error(`Unexpected request: ${url}`);
    }));

    const { result } = renderHook(() => useOccupancyData(1_000));
    await flushRequests();
    await act(async () => {
      await vi.advanceTimersByTimeAsync(1_000);
    });

    expect(result.current.occupancy).toBe(2);
    expect(result.current.occupancySeries.map((point) => point.count)).toEqual([2]);
  });

  it("rejects a first API reading older than the retained two-hour window", async () => {
    const stale = statusReading(9);
    stale.timestamp = new Date(
      START_TIME - MAX_OCCUPANCY_HISTORY_MS - 1,
    ).toISOString();
    let statusReturned = false;
    vi.stubGlobal("fetch", vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/occupancy/status")) {
        statusReturned = true;
        return jsonResponse(stale);
      }
      if (url.endsWith("/radar/latest")) return jsonResponse({ devices: [] });
      if (url.includes("/occupancy/events")) return jsonResponse({ events: [] });
      if (url.endsWith("/bluetooth/tags")) return jsonResponse({ tags: [] });
      if (url.endsWith("/co2/latest")) return jsonResponse({ devices: [] });
      throw new Error(`Unexpected request: ${url}`);
    }));

    const { result } = renderHook(() => useOccupancyData(1_000));
    await flushRequests();

    expect(statusReturned).toBe(true);
    expect(result.current.occupancy).toBe(0);
    expect(result.current.occupancySeries).toEqual([]);
    expect(result.current.isLive).toBe(false);
  });

  it("clears its interval and aborts pending requests on unmount", () => {
    const signals: AbortSignal[] = [];
    vi.stubGlobal("fetch", vi.fn((_input: RequestInfo | URL, init?: RequestInit) => {
      if (init?.signal) signals.push(init.signal);
      return new Promise<Response>(() => {});
    }));

    const { unmount } = renderHook(() => useOccupancyData(1_000));
    expect(vi.getTimerCount()).toBeGreaterThan(0);
    unmount();

    expect(vi.getTimerCount()).toBe(0);
    expect(signals.length).toBeGreaterThan(0);
    expect(signals.every((signal) => signal.aborted)).toBe(true);
  });
});
