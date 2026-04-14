const STYLES: Record<string, string> = {
  raw: "bg-slate-100 text-slate-700",
  quarantine: "bg-rose-100 text-rose-800",
  bronze: "bg-amber-100 text-amber-900",
  silver: "bg-slate-200 text-slate-800",
  gold: "bg-yellow-100 text-yellow-900",
};

export default function StageBadge({ stage }: { stage: string | null | undefined }) {
  if (!stage) return <span className="text-slate-400">—</span>;
  const cls = STYLES[stage] ?? "bg-navy-100 text-navy-800";
  return (
    <span
      className={`inline-flex items-center rounded px-2 py-0.5 text-[11px] font-semibold uppercase tracking-wide ${cls}`}
    >
      {stage}
    </span>
  );
}
