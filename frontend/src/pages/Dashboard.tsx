import AppLayout from "../layouts/AppLayout";

export default function Dashboard() {
  const cards = [
    ["Current Occupancy", "18", "Room Available"],
    ["Radar Presence", "Detected", "mmWave active"],
    ["Temperature", "23°C", "Normal"],
    ["Motion", "Yes", "PIR detected"],
  ];

  const trend = [8, 12, 15, 20, 18, 22, 16];

  return (
    <AppLayout>
      <p className="text-xs uppercase tracking-[0.3em] text-emerald-400 md:text-sm">
        Privacy Preserving Monitor
      </p>

      <h1 className="mt-3 text-3xl font-bold md:text-5xl">
        Room Occupancy Dashboard
      </h1>

      <p className="mt-3 text-sm text-slate-400 md:text-base">
        Live sensor-based room occupancy overview
      </p>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map(([title, value, sub]) => (
          <div
            key={title}
            className="rounded-2xl border border-emerald-400/20 bg-white/5 p-5 shadow-[0_0_25px_rgba(52,211,153,0.06)]"
          >
            <p className="text-sm text-slate-400 md:text-base">{title}</p>

            <h2 className="mt-3 text-4xl font-bold text-emerald-300 md:text-5xl">
              {value}
            </h2>

            <p className="mt-2 text-sm text-emerald-400 md:text-base">{sub}</p>
          </div>
        ))}
      </div>

      <div className="mt-7 rounded-2xl border border-emerald-400/20 bg-white/5 p-5 shadow-[0_0_25px_rgba(52,211,153,0.06)] md:p-7">
        <h2 className="text-xl font-bold md:text-2xl">Occupancy Trend</h2>

        <div className="mt-6 flex h-56 items-end gap-3 overflow-x-auto border-b border-l border-emerald-400/20 p-4 md:h-64 md:gap-5">
          {trend.map((value, index) => (
            <div
              key={index}
              className="flex min-w-[65px] flex-1 flex-col items-center"
            >
              <div
                className="w-full max-w-20 rounded-t-xl bg-emerald-400 shadow-[0_0_20px_rgba(52,211,153,0.45)]"
                style={{ height: `${value * 7}px` }}
              />

              <span className="mt-3 text-xs text-slate-400 md:text-sm">
                {9 + index}:00
              </span>
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}
