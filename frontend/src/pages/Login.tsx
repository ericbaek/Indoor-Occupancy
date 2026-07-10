type LoginProps = {
  onLogin: () => void;
};

export default function Login({ onLogin }: LoginProps) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#07130f] px-6">
      <div className="w-full max-w-md rounded-3xl border border-emerald-400/20 bg-white/5 p-8 shadow-[0_0_35px_rgba(52,211,153,0.08)] backdrop-blur">

        <p className="text-center text-xs uppercase tracking-[0.35em] text-emerald-400">
          Privacy Preserving Monitor
        </p>

        <h1 className="mt-4 text-center text-5xl font-bold text-white">
          RoomSense
        </h1>

        <p className="mt-3 text-center text-slate-400">
          Sign in to access the Room Occupancy Dashboard
        </p>

        <form className="mt-10 space-y-6">

          <div>
            <label className="mb-2 block text-sm text-slate-300">
              Email
            </label>

            <input
              type="email"
              placeholder="Enter your email"
              className="w-full rounded-xl border border-emerald-400/20 bg-[#0d1b16] px-4 py-3 text-white placeholder:text-slate-500 outline-none transition focus:border-emerald-400"
            />
          </div>

          <div>
            <label className="mb-2 block text-sm text-slate-300">
              Password
            </label>

            <input
              type="password"
              placeholder="Enter your password"
              className="w-full rounded-xl border border-emerald-400/20 bg-[#0d1b16] px-4 py-3 text-white placeholder:text-slate-500 outline-none transition focus:border-emerald-400"
            />
          </div>

          <button
            type="button"
            onClick={onLogin}
            className="mt-2 w-full rounded-xl bg-emerald-400 py-3 text-lg font-semibold text-slate-950 transition duration-300 hover:bg-emerald-300 hover:shadow-[0_0_20px_rgba(52,211,153,0.5)]"
          >
            Login
          </button>

        </form>

      </div>
    </div>
  );
}