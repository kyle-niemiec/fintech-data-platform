import { useEffect, useState } from "react";
import { NavLink, Link, useLocation } from "react-router-dom";
import GitHubRepoBlock from "./GitHubRepoBlock";

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

/**
 * Render the top navigation bar.
 */
export default function TopNav() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  /**
   * Close the mobile menu whenever the route changes to prevent it from staying
   * open when navigating to a new page.
   */
  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  /**
   * Determine the appropriate CSS classes for desktop and mobile navigation
   * links based on whether they are active (i.e., match the current route).
   * 
   * @param {object} param0 An object containing the `isActive` property, which indicates if the link is active.
   * 
   * @returns {string} A string of CSS classes to style the navigation link, with different styles for active and inactive states.
   */
  const desktopLinkClass = ({ isActive }: { isActive: boolean }) =>
    `${linkBase} ${
      isActive
        ? "bg-white/10 text-white"
        : "text-navy-100 hover:bg-white/5 hover:text-white"
    }`;

  /**
   * Use the same styling for mobile links as desktop links, but with adjustments
   * for mobile layout.
   * 
   * @param {object} param0 An object containing the `isActive` property.
   * 
   * @returns {string} A string of CSS classes to style the mobile navigation link
   */
  const mobileLinkClass = ({ isActive }: { isActive: boolean }) =>
    `block rounded-md px-3 py-2 text-base font-medium transition-colors ${
      isActive
        ? "bg-white/10 text-white"
        : "text-navy-100 hover:bg-white/5 hover:text-white"
    }`;

  /**
   * Render the top navigation bar with links to different sections of the application,
   * a GitHub repository block, and an environment indicator.
   */
  return (
    <header className="border-b border-navy-800 bg-navy-900 text-white">
      <div className="mx-auto flex max-w-7xl items-center gap-4 px-6 py-3 lg:gap-8">
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
        <nav className="hidden items-center gap-1 lg:flex">
          {NAV_LINKS.map(({ to, label, end }) => (
            <NavLink key={to} to={to} end={end} className={desktopLinkClass}>
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="ml-auto flex items-center gap-3">
          <div className="hidden lg:block">
            <GitHubRepoBlock />
          </div>
          <button
            type="button"
            onClick={() => setIsMobileMenuOpen((open) => !open)}
            aria-expanded={isMobileMenuOpen}
            aria-label={isMobileMenuOpen ? "Close menu" : "Open menu"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-navy-400/40 bg-navy-800 text-navy-100 transition-colors hover:bg-navy-700 hover:text-white lg:hidden"
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="h-5 w-5"
              aria-hidden="true"
            >
              {isMobileMenuOpen ? (
                <>
                  <line x1="6" y1="6" x2="18" y2="18" />
                  <line x1="6" y1="18" x2="18" y2="6" />
                </>
              ) : (
                <>
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </div>
      {isMobileMenuOpen && (
        <div className="border-t border-navy-800 lg:hidden">
          <nav className="mx-auto flex max-w-7xl flex-col gap-1 px-6 py-3">
            {NAV_LINKS.map(({ to, label, end }) => (
              <NavLink key={to} to={to} end={end} className={mobileLinkClass}>
                {label}
              </NavLink>
            ))}
          </nav>
          <div className="mx-auto max-w-7xl px-6 pb-4">
            <GitHubRepoBlock />
          </div>
        </div>
      )}
    </header>
  );
}
