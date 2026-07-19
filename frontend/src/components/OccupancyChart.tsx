import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import type { OccupancyPoint, OccupancyRange } from "../data";
import "./OccupancyChart.css";

const RANGES: OccupancyRange[] = ["5m", "10m", "30m", "1H", "2H"];

const RANGE_SUBTITLE: Record<OccupancyRange, string> = {
  "5m": "Last 5 minutes",
  "10m": "Last 10 minutes",
  "30m": "Last 30 minutes",
  "1H": "Last hour",
  "2H": "Last 2 hours",
};

export default function OccupancyChart({
  dataByRange,
  capacity,
}: {
  /** Real backend event history, bucketed per range by useOccupancyData(). */
  dataByRange: Record<OccupancyRange, OccupancyPoint[]>;
  capacity: number;
}) {
  const [range, setRange] = useState<OccupancyRange>("30m");
  const data = dataByRange[range];

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div>
          <div className="chart-title">Occupancy over time</div>
          <div className="chart-sub">{RANGE_SUBTITLE[range]} &middot; PIR + mmWave</div>
        </div>
        <div className="chart-ranges">
          {RANGES.map((r) => (
            <button
              key={r}
              className={`range-btn${r === range ? " range-btn-active" : ""}`}
              onClick={() => setRange(r)}
              aria-pressed={r === range}
            >
              {r}
            </button>
          ))}
        </div>
      </div>

      <div className="chart-plot">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="occFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#17B3A3" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#17B3A3" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 5" stroke="var(--border)" vertical={false} />
          <XAxis dataKey="t" tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} width={30} allowDecimals={false} />
          <ReferenceLine y={capacity} stroke="#C2432B" strokeDasharray="4 4" label={{ value: `Capacity (${capacity})`, position: "insideTopRight", fill: "#C2432B", fontSize: 10.5 }} />
          <Tooltip
            contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", color: "var(--text)", fontSize: 12, fontFamily: "Inter" }}
            labelStyle={{ fontWeight: 600, color: "var(--text)" }}
          />
          <Area type="monotone" dataKey="count" stroke="#17B3A3" strokeWidth={2.25} fill="url(#occFill)" name="People" isAnimationActive={false} />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}