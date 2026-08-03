import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { OccupancyPoint } from "../data";
import OccupancyChart from "./OccupancyChart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => children,
  AreaChart: ({
    data,
  }: {
    data: OccupancyPoint[];
  }) => (
    <div data-testid="occupancy-area-chart" data-points={JSON.stringify(data)} />
  ),
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

const NOW = Date.parse("2026-08-03T12:00:00.000Z");

describe("OccupancyChart ranges", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(NOW);
  });

  afterEach(() => {
    cleanup();
    vi.useRealTimers();
  });

  it("shows only readings from the previous five real minutes when 5m is selected", () => {
    const data: OccupancyPoint[] = [
      { timestamp: NOW - 6 * 60 * 1000, count: 1 },
      { timestamp: NOW - 5 * 60 * 1000, count: 2 },
      { timestamp: NOW - 10 * 1000, count: 3 },
      { timestamp: NOW, count: 4 },
    ];

    render(<OccupancyChart data={data} capacity={40} />);
    fireEvent.click(screen.getByRole("button", { name: "5m" }));

    const points = JSON.parse(
      screen.getByTestId("occupancy-area-chart").dataset.points ?? "[]",
    ) as OccupancyPoint[];
    expect(points).toEqual(data.slice(1));
  });
});
