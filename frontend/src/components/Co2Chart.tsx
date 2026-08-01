import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ReferenceLine, ResponsiveContainer } from "recharts";
import type { Co2Point } from "../data";
import "./OccupancyChart.css";

/** ASHRAE-based reference line — above this, elevated CO2 suggests poor ventilation. */
const ELEVATED_PPM = 800;

export default function Co2Chart({
  data,
  deviceId,
}: {
  /** Recent readings for one CO2 device, oldest first. */
  data: Co2Point[];
  deviceId: string | null;
}) {
  const hasData = data.length > 0;

  return (
    <div className="chart-card">
      <div className="chart-head">
        <div>
          <div className="chart-title">CO2 trend</div>
          <div className="chart-sub">
            {deviceId ? `SCD41 \u00b7 ${deviceId}` : "No CO2 sensor reporting yet"}
          </div>
        </div>
      </div>

      <div className="chart-plot">
        {hasData ? (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 8, right: 8, left: 4, bottom: 0 }}>
              <defs>
                <linearGradient id="co2Fill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#8B5CF6" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#8B5CF6" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 5" stroke="var(--border)" vertical={false} />
              <XAxis dataKey="t" tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} />
              <YAxis tick={{ fontSize: 11, fill: "var(--text-faint)" }} axisLine={false} tickLine={false} width={38} allowDecimals={false} />
              <ReferenceLine
                y={ELEVATED_PPM}
                stroke="#C2432B"
                strokeDasharray="4 4"
                label={{ value: `${ELEVATED_PPM} ppm`, position: "insideTopRight", fill: "#C2432B", fontSize: 10.5 }}
              />
              <Tooltip
                contentStyle={{ borderRadius: 10, border: "1px solid var(--border)", background: "var(--card)", color: "var(--text)", fontSize: 12, fontFamily: "Inter" }}
                labelStyle={{ fontWeight: 600, color: "var(--text)" }}
                formatter={(value) => [`${value} ppm`, "CO2"]}
              />
              <Area type="monotone" dataKey="ppm" stroke="#8B5CF6" strokeWidth={2.25} fill="url(#co2Fill)" name="CO2" isAnimationActive={false} />
            </AreaChart>
          </ResponsiveContainer>
        ) : (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: "100%", color: "var(--text-faint)", fontSize: 13 }}>
            Waiting for CO2 readings
          </div>
        )}
      </div>
    </div>
  );
}