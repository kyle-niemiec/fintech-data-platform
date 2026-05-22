import { NavLink } from "react-router-dom";

const linkBase =
  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors";

export default function TopNav() {
  return (
    <header className="border-b border-navy-800 bg-navy-900 text-white">
      <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white font-bold text-navy-900">
            M
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-wide">Meridian</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-navy-200">
              Data Platform
            </div>
          </div>
        </div>
        <nav className="flex items-center gap-1">
          <NavLink
            to="/"
            end
            className={({ isActive }) =>
              `${linkBase} ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-navy-100 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            Runs
          </NavLink>
          <NavLink
            to="/oltp/transactions"
            className={({ isActive }) =>
              `${linkBase} ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-navy-100 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            Recent Transactions
          </NavLink>
          <NavLink
            to="/alerts"
            className={({ isActive }) =>
              `${linkBase} ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-navy-100 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            Alerts
          </NavLink>
          <NavLink
            to="/backfill"
            className={({ isActive }) =>
              `${linkBase} ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-navy-100 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            Backfill
          </NavLink>
          <NavLink
            to="/metrics"
            className={({ isActive }) =>
              `${linkBase} ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-navy-100 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            Metrics
          </NavLink>
          <NavLink
            to="/demo/upload"
            className={({ isActive }) =>
              `${linkBase} ${
                isActive
                  ? "bg-white/10 text-white"
                  : "text-navy-100 hover:bg-white/5 hover:text-white"
              }`
            }
          >
            Demo Upload
          </NavLink>
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <span className="rounded-full border border-navy-400/40 bg-navy-800 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-navy-100">
            env · local
          </span>
        </div>
      </div>
    </header>
  );
}
