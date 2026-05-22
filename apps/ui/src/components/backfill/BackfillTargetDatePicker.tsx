interface Props {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: "date" | "datetime-local";
}

export default function BackfillTargetDatePicker({ label, value, onChange, type = "date" }: Props) {
  const max =
    type === "date"
      ? new Date(Date.now() - 86_400_000).toISOString().slice(0, 10)
      : new Date(Date.now() - 60_000).toISOString().slice(0, 16);

  return (
    <label className="text-sm">
      <div className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-navy-500">
        {label}
      </div>
      <input
        type={type}
        max={max}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-navy-500 focus:outline-none focus:ring-1 focus:ring-navy-500"
      />
    </label>
  );
}
