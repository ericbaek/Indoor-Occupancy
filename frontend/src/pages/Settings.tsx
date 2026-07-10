import AppLayout from "../layouts/AppLayout";

export default function Settings() {
  return (
    <AppLayout>
      <p className="text-sm uppercase tracking-[0.3em] text-emerald-400">
        System Controls
      </p>
      <h1 className="mt-3 text-5xl font-bold">Settings</h1>
      <p className="mt-3 text-slate-400">
        Configure alert limits and monitoring preferences.
      </p>

      <div className="mt-10 max-w-3xl rounded-3xl border border-emerald-400/20 bg-white/5 p-8">
        <div className="space-y-6">
          <div>
            <label className="text-slate-300">Occupancy Limit</label>
            <input
              type="number"
              defaultValue="25"
              className="mt-2 w-full rounded-xl border border-emerald-400/20 bg-[#07130f] px-4 py-3 text-white outline-none focus:border-emerald-400"
            />
          </div>

          <div>
            <label className="text-slate-300">CO₂ Alert Threshold</label>
            <input
              type="number"
              defaultValue="1000"
              className="mt-2 w-full rounded-xl border border-emerald-400/20 bg-[#07130f] px-4 py-3 text-white outline-none focus:border-emerald-400"
            />
          </div>

          <div>
            <label className="text-slate-300">Refresh Interval</label>
            <select className="mt-2 w-full rounded-xl border border-emerald-400/20 bg-[#07130f] px-4 py-3 text-white outline-none focus:border-emerald-400">
              <option>Every 5 seconds</option>
              <option>Every 10 seconds</option>
              <option>Every 30 seconds</option>
            </select>
          </div>

          <button className="rounded-xl bg-emerald-400 px-6 py-3 font-semibold text-slate-950">
            Save Settings
          </button>
        </div>
      </div>
    </AppLayout>
  );
}