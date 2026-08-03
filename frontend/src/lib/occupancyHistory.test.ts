import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  appendOccupancyPoint,
  filterOccupancyPoints,
  MAX_OCCUPANCY_HISTORY_MS,
  resolveOccupancyTimestamp,
} from "./occupancyHistory";

const NOW = Date.parse("2026-08-03T12:00:00.000Z");

describe("occupancy history", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("keeps only readings from the previous five real minutes", () => {
    const history = [
      { timestamp: NOW - 300_001, count: 1 },
      { timestamp: NOW - 300_000, count: 2 },
      { timestamp: NOW - 1_000, count: 3 },
      { timestamp: NOW, count: 4 },
    ];

    expect(filterOccupancyPoints(history, "5m")).toEqual(history.slice(1));
  });

  it("orders points, replaces duplicate timestamps, and limits history to two hours", () => {
    const history = [
      { timestamp: NOW - MAX_OCCUPANCY_HISTORY_MS - 1, count: 9 },
      { timestamp: NOW - 1_000, count: 1 },
      { timestamp: NOW - 2_000, count: 2 },
    ];

    const appended = appendOccupancyPoint(
      history,
      { timestamp: NOW - 1_000, count: 7 },
    );

    expect(appended).toEqual([
      { timestamp: NOW - 2_000, count: 2 },
      { timestamp: NOW - 1_000, count: 7 },
    ]);
  });

  it("prefers a valid API timestamp and otherwise uses receipt time", () => {
    const apiTime = "2026-08-03T11:59:58.000Z";
    expect(resolveOccupancyTimestamp({ timestamp: apiTime }, NOW)).toBe(Date.parse(apiTime));
    expect(resolveOccupancyTimestamp({ timestamp: "not-a-date" }, NOW)).toBe(NOW);
  });
});
