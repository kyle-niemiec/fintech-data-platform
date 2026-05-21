const STYLES: Record<string, string> = {
  high: "bg-rose-100 text-rose-800 ring-rose-200",
  medium: "bg-amber-100 text-amber-800 ring-amber-200",
  low: "bg-sky-100 text-sky-800 ring-sky-200",
};

export default function SeverityBadge({ severity }: { severity: string }) {
  const cls = STYLES[severity] ?? "bg-slate-100 text-slate-700 ring-slate-200";
  return (
    <span
      className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium uppercase tracking-wide ring-1 ring-inset ${cls}`}
    >
      {severity}
    </span>
  );
}
