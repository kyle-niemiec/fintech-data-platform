import { Outlet } from "react-router-dom";
import TopNav from "./components/layout/TopNav";

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
        <div className="mx-auto max-w-7xl px-6 py-4 text-xs text-navy-600">
          Meridian Fintech Data Platform &middot; Demo Console
          {releaseTag ? ` · Version ${releaseTag}` : ""}
        </div>
      </footer>
    </div>
  );
}
