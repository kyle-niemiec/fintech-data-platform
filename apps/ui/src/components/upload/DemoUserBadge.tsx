export default function DemoUserBadge({ email }: { email: string }) {
  const initials = email
    .split("@")[0]
    .split(".")
    .map((p) => p.charAt(0).toUpperCase())
    .slice(0, 2)
    .join("");
  return (
    <div className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1">
      <div className="flex h-6 w-6 items-center justify-center rounded-full bg-navy-700 text-[11px] font-semibold text-white">
        {initials}
      </div>
      <span className="font-mono text-xs text-navy-800">{email}</span>
    </div>
  );
}
