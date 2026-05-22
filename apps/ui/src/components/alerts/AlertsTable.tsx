import { useNavigate } from "react-router-dom";
import MonoId from "../common/MonoId";
import RelativeTime from "../common/RelativeTime";
import SortableHeader from "../common/SortableHeader";
import SeverityBadge from "./SeverityBadge";
import type { SortDir, SortState } from "../../lib/queryKeys";
import type { AlertItem } from "../../types/api";

function detailsPreview(details: Record<string, unknown> | null | undefined): string {
  const entries = Object.entries(details ?? {});
  if (entries.length === 0) return "";
  return entries
    .slice(0, 4)
    .map(([k, v]) => `${k}=${typeof v === "object" ? JSON.stringify(v) : String(v)}`)
    .join("  ·  ");
}

export default function AlertsTable({
  alerts,
  hideRun = false,
  sort,
  onSort,
}: {
  alerts: AlertItem[];
  hideRun?: boolean;
  sort?: SortState;
  onSort?: (column: string, dir: SortDir) => void;
}) {
  const navigate = useNavigate();
  const th = (column: string, label: string, initialDir: SortDir) =>
    sort && onSort ? (
      <SortableHeader
        column={column}
        label={label}
        active={sort.sort === column}
        dir={sort.dir}
        onSort={onSort}
        initialDir={initialDir}
      />
    ) : (
      <th>{label}</th>
    );
  return (
    <div className="card overflow-hidden">
      <table className="table-default">
        <thead className="bg-slate-50">
          <tr>
            {th("occurred", "Occurred", "desc")}
            {th("severity", "Severity", "asc")}
            {th("category", "Category", "asc")}
            <th>Summary</th>
            {hideRun ? null : th("run", "Run", "asc")}
          </tr>
        </thead>
        <tbody>
          {alerts.map((a) => {
            const preview = detailsPreview(a.details);
            return (
              <tr
                key={a.alert_id}
                onClick={hideRun ? undefined : () => navigate(`/runs/${a.run_id}`)}
                className={hideRun ? undefined : "cursor-pointer"}
              >
                <td>
                  <RelativeTime iso={a.occurred_at} />
                </td>
                <td>
                  <SeverityBadge severity={a.severity} />
                </td>
                <td className="font-mono text-xs text-navy-700">{a.category}</td>
                <td>
                  <div className="text-sm text-navy-900">{a.summary}</div>
                  {preview ? (
                    <div className="mt-0.5 font-mono text-xs text-navy-500">{preview}</div>
                  ) : null}
                </td>
                {hideRun ? null : (
                  <td>
                    <MonoId value={a.run_id} short />
                  </td>
                )}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
