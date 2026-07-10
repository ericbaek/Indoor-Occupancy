import { Link, useLocation } from "react-router-dom";

type Props = {
  children: React.ReactNode;
};

export default function AppLayout({ children }: Props) {
  const location = useLocation();

  const links = [
    ["Dashboard", "/dashboard"],
    ["Room Details", "/room-details"],
    ["History", "/history"],
    ["Settings", "/settings"],
  ];

  return (
    <div className="min-h-screen bg-[#07130f] text-white">
      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="w-full border-b border-emerald-500/20 bg-[#062019] p-4 md:min-h-screen md:w-64 md:border-b-0 md:border-r md:p-6">
          <h2 className="text-xl font-bold text-emerald-400 md:text-2xl">
            RoomSense
          </h2>

          <nav className="mt-5 flex gap-2 overflow-x-auto md:mt-10 md:block md:space-y-3">
            {links.map(([label, path]) => (
              <Link
                key={path}
                to={path}
                className={`whitespace-nowrap rounded-xl px-4 py-3 text-sm font-semibold transition-all md:block md:text-base ${
                  location.pathname === path
                    ? "bg-emerald-400 text-slate-950"
                    : "text-slate-300 hover:bg-emerald-400/10"
                }`}
              >
                {label}
              </Link>
            ))}

            <Link
              to="/login"
              className="whitespace-nowrap rounded-xl border border-red-500/30 px-4 py-3 text-sm font-semibold text-red-400 hover:bg-red-500/20 md:mt-10 md:block md:text-center md:text-base"
            >
              Logout
            </Link>
          </nav>
        </aside>

        <main className="flex-1 px-5 py-7 md:px-8 lg:px-12">
          {children}
        </main>
      </div>
    </div>
  );
}