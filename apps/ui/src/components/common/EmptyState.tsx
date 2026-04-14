import type { ReactNode } from "react";

export default function EmptyState({
  title,
  description,
  action,
}: {
  title: string;
  description?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="card card-pad flex flex-col items-center justify-center gap-2 py-12 text-center">
      <div className="text-sm font-semibold text-navy-900">{title}</div>
      {description ? (
        <div className="max-w-md text-sm text-navy-600">{description}</div>
      ) : null}
      {action ? <div className="mt-2">{action}</div> : null}
    </div>
  );
}
