import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import type { OccupancyPoint } from "../data";
import "./OccupancyChart.css";

const RANGES = ["1H", "6H", "1D", "1W", "1M"];

export default function OccupancyChart({ data, capacity }: { data: OccupancyPoint[]; capacity: number }) {
  return (
    <div className="chart-card">
      <div className="chart-head">
        <div>
          <div className="chart-title">Occupancy over time</div>
          <div className="chart-sub">Sensor-fused count &middot; K17-101</div>
        </div>
        <div className="chart-ranges">
          {RANGES.map((r) => (
            <button key={r} className={`range-btn${r === "1D" ? " range-btn-active" : ""}`}>
              {r}
            </button>
          ))}
        </div>
      </div>

      <ResponsiveContainer width="100%" height={230}>
        <AreaChart data={data} margin={{ top: 8, right: 8, left: -18, bottom: 0 }}>
          <defs>
            <linearGradient id="occFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="#17B3A3" stopOpacity={0.28} />
              <stop offset="100%" stopColor="#17B3A3" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid strokeDasharray="3 5" stroke="#E4E8E6" vertical={false} />
          <XAxis dataKey="t" tick={{ fontSize: 11, fill: "#939BA5" }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fontSize: 11, fill: "#939BA5" }} axisLine={false} tickLine={false} width={30} />
          <ReferenceLine y={capacity} stroke="#C2432B" strokeDasharray="4 4" label={{ value: `Capacity (${capacity})`, position: "insideTopRight", fill: "#C2432B", fontSize: 10.5 }} />
          <Tooltip
            contentStyle={{ borderRadius: 10, border: "1px solid #E4E8E6", fontSize: 12, fontFamily: "Inter" }}
            labelStyle={{ fontWeight: 600 }}
          />
          <Area type="monotone" dataKey="count" stroke="#17B3A3" strokeWidth={2.25} fill="url(#occFill)" name="People" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
