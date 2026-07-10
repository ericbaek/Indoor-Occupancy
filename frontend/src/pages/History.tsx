import AppLayout from "../layouts/AppLayout";

export default function History() {
  return (
    <AppLayout>
      <p className="text-sm uppercase tracking-[0.3em] text-emerald-400">
        Occupancy Records
      </p>
      <h1 className="mt-3 text-5xl font-bold">History</h1>
      <p className="mt-3 text-slate-400">
        Past room occupancy trends and sensor readings.
      </p>

      <div className="mt-10 rounded-3xl border border-emerald-400/20 bg-white/5 p-8">
        <h2 className="text-2xl font-bold">Today&apos;s Occupancy</h2>

        <div className="mt-8 flex h-72 items-end gap-5 border-b border-l border-emerald-400/20 p-5">
          {[6, 10, 14, 22, 18, 25, 12].map((value, index) => (
            <div key={index} className="flex flex-1 flex-col items-center">
              <div
                className="w-full rounded-t-xl bg-emerald-400 shadow-[0_0_25px_rgba(52,211,153,0.55)]"
                style={{ height: `${value * 8}px` }}
              />
              <span className="mt-3 text-sm text-slate-400">
                {9 + index}:00
              </span>
            </div>
          ))}
        </div>
      </div>
    </AppLayout>
  );
}