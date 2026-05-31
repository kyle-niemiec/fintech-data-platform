import { Outlet } from "react-router-dom";
import TopNav from "./components/layout/TopNav";
import SessionTimer from "./components/layout/SessionTimer";
import ShutdownOverlay from "./components/layout/ShutdownOverlay";

/**
 * Parses the release tag from environment variables (e.g., "v1.0.0")
 */
const releaseTag = (() => {
  const value = (import.meta.env.VITE_RELEASE_TAG as string | undefined)?.trim();

  if (! value) {
    return undefined;
  }

  return /^v\d+\.\d+\.\d+$/.test(value) ? value : undefined;
})();

const APP_ENV =
  (import.meta.env.VITE_APP_ENV ?? "local").trim() || "local";

/**
 * Root application component that serves as the main layout wrapper for all pages.
 *
 * @returns The application wrapper JSX
 */
export default function App() {
  return (
    <div className="flex min-h-full flex-col">
      <TopNav />

      <main className="mx-auto w-full max-w-7xl flex-1 px-6 py-8">
        <Outlet />
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-3 px-6 py-4 text-xs text-navy-600">
          <div>
            Meridian Fintech Demo
            {releaseTag ? ` · Version ${releaseTag}` : ""}
          </div>

          <div className="flex items-center gap-2">
            <SessionTimer />

            <span className="rounded-full border border-navy-200 bg-slate-100 px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-navy-700">
              env · {APP_ENV}
            </span>
          </div>
        </div>
      </footer>

      <ShutdownOverlay />
    </div>
  );
}
