import type { RunStatus } from "../../types/api";

const STYLES: Record<string, string> = {
  completed: "bg-emerald-100 text-emerald-800 ring-emerald-200",
  running: "bg-amber-100 text-amber-800 ring-amber-200",
  failed: "bg-rose-100 text-rose-800 ring-rose-200",
  scan_failed: "bg-rose-100 text-rose-800 ring-rose-200",
  quarantined: "bg-rose-100 text-rose-800 ring-rose-200",
};

const LABELS: Record<string, string> = {
  scan_failed: "scan failed",
};

export default function StatusPill({ status }: { status: RunStatus }) {
  const cls = STYLES[status] ?? "bg-slate-100 text-slate-700 ring-slate-200";
  const label = LABELS[status] ?? status;
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset ${cls}`}
    >
      {label}
    </span>
  );
}
