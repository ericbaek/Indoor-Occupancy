import AppLayout from "../layouts/AppLayout";

export default function RoomDetails() {
  const sensors = [
    ["CO₂ Sensor", "SCD41", "640 ppm", "Healthy air level"],
    ["PIR Motion Sensor", "Active", "Motion detected", "Recent movement found"],
    ["mmWave Radar", "Optional", "Not connected", "Future enhancement"],
    ["Confidence Score", "Model estimate", "87%", "Reliable occupancy reading"],
  ];

  return (
    <AppLayout>
      <p className="text-sm uppercase tracking-[0.3em] text-emerald-400">
        Sensor Overview
      </p>
      <h1 className="mt-3 text-5xl font-bold">Room Details</h1>
      <p className="mt-3 text-slate-400">
        Sensor readings used to estimate room occupancy without tracking people.
      </p>

      <div className="mt-10 grid grid-cols-1 gap-6 md:grid-cols-2">
        {sensors.map(([title, type, value, desc]) => (
          <div
            key={title}
            className="rounded-3xl border border-emerald-400/20 bg-white/5 p-8 shadow-[0_0_35px_rgba(52,211,153,0.08)]"
          >
            <p className="text-slate-400">{type}</p>
            <h2 className="mt-3 text-3xl font-bold">{title}</h2>
            <p className="mt-5 text-4xl font-bold text-emerald-300">{value}</p>
            <p className="mt-3 text-slate-400">{desc}</p>
          </div>
        ))}
      </div>
    </AppLayout>
  );
}