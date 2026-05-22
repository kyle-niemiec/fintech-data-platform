import { NavLink, Link } from "react-router-dom";

const linkBase =
  "rounded-md px-3 py-1.5 text-sm font-medium transition-colors";

const NAV_LINKS: { to: string; label: string; end?: boolean }[] = [
  { to: "/", label: "Overview", end: true },
  { to: "/runs", label: "Runs" },
  { to: "/oltp/transactions", label: "Transactions" },
  { to: "/demo/upload", label: "Excel Upload" },
  { to: "/backfill", label: "Backfill" },
  { to: "/alerts", label: "Alerts" },
  { to: "/metrics", label: "Metrics" },
];

export default function TopNav() {
  return (
    <header className="border-b border-navy-800 bg-navy-900 text-white">
      <div className="mx-auto flex max-w-7xl items-center gap-8 px-6 py-3">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-md bg-white font-bold text-navy-900">
            M
          </div>
          <div className="leading-tight">
            <div className="text-sm font-semibold tracking-wide">Meridian</div>
            <div className="text-[11px] uppercase tracking-[0.14em] text-navy-200">
              Data Platform
            </div>
          </div>
        </Link>
        <nav className="flex items-center gap-1">
          {NAV_LINKS.map(({ to, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                `${linkBase} ${
                  isActive
                    ? "bg-white/10 text-white"
                    : "text-navy-100 hover:bg-white/5 hover:text-white"
                }`
              }
            >
              {label}
            </NavLink>
          ))}
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
