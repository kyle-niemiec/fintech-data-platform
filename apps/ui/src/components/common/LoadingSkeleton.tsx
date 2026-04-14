export default function LoadingSkeleton({ rows = 4 }: { rows?: number }) {
  return (
    <div className="card card-pad space-y-2">
      {Array.from({ length: rows }).map((_, i) => (
        <div
          key={i}
          className="h-4 w-full animate-pulse rounded bg-slate-100"
          style={{ width: `${70 + ((i * 13) % 30)}%` }}
        />
      ))}
    </div>
  );
}
