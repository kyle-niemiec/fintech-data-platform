import { Outlet } from "react-router-dom";
import TopNav from "./components/layout/TopNav";

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
        </div>
      </footer>
    </div>
  );
}
