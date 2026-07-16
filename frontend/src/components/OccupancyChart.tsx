import { useState } from "react";
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import type { OccupancyPoint, OccupancyRange } from "../data";
import "./OccupancyChart.css";

const RANGES: OccupancyRange[] = ["1H", "6H", "1D", "1W", "1M"];

const RANGE_SUBTITLE: Record<OccupancyRange, string> = {
  "1H": "Last hour",
  "6H": "Last 6 hours",
  "1D": "Last 24 hours",
  "1W": "Last 7 days",
  "1M": "Last 30 days",
};

export default function OccupancyChart({
  dataByRange,
  capacity,
}: {
  /** Real backend event history, bucketed per range by useOccupancyData(). */
  dataByRange: Record<OccupancyRange, OccupancyPoint[]>;
  capacity: number;
}) {
  const [range, setRange] = useState<OccupancyRange>("1D");
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
