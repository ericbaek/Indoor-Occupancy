import type { ReactNode } from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { OccupancyPoint, OccupancyRange } from "../data";
import OccupancyChart from "./OccupancyChart";

vi.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: ReactNode }) => children,
  AreaChart: ({ data }: { data: OccupancyPoint[] }) => (
    <div data-testid="occupancy-area-chart" data-points={JSON.stringify(data)} />
  ),
  Area: () => null,
  XAxis: () => null,
  YAxis: () => null,
  CartesianGrid: () => null,
  Tooltip: () => null,
  ReferenceLine: () => null,
}));

afterEach(cleanup);

describe("OccupancyChart", () => {
  it("shows the selected range", () => {
    const empty: OccupancyPoint[] = [];
    const fiveMinutes = [
      { t: "11:59:00", count: 2 },
      { t: "12:00:00", count: 4 },
    ];
    const dataByRange: Record<OccupancyRange, OccupancyPoint[]> = {
      "5m": fiveMinutes,
      "10m": empty,
      "30m": [{ t: "11:30", count: 1 }],
      "1H": empty,
      "2H": empty,
    };

    render(<OccupancyChart dataByRange={dataByRange} capacity={40} />);
    fireEvent.click(screen.getByRole("button", { name: "5m" }));

    const points = JSON.parse(
      screen.getByTestId("occupancy-area-chart").dataset.points ?? "[]",
    ) as OccupancyPoint[];
    expect(points).toEqual(fiveMinutes);
  });
});
