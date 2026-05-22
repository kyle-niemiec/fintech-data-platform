import { pipelineDisplayNameFor } from "../../lib/pipelineColors";
import type { PipelineAnalyticsItem } from "../../types/api";

function fmt(s: number | null): string {
  if (s === null || s === undefined) return "—";
  if (s < 60) return `${s.toFixed(1)}s`;
  return `${(s / 60).toFixed(1)}m`;
}

export default function PipelineAnalyticsTable({
  items,
}: {
  items: PipelineAnalyticsItem[];
}) {
  return (
    <div className="overflow-hidden rounded-lg border border-slate-200">
      <table className="table-default">
        <thead className="bg-slate-50">
          <tr>
            <th>Pipeline</th>
            <th className="text-right">Completed</th>
            <th className="text-right">Failed</th>
            <th className="text-right">Quarantined</th>
            <th className="text-right">Avg duration</th>
            <th className="text-right">High alerts</th>
            <th className="text-right">Med alerts</th>
          </tr>
        </thead>
        <tbody>
          {items.map((row) => (
            <tr key={row.pipeline_name}>
              <td>
                <span className="font-medium">
                  {pipelineDisplayNameFor(row.pipeline_name)}
                </span>
                <span className="ml-1.5 font-mono text-[11px] text-navy-400">
                  {row.pipeline_name}
                </span>
              </td>
              <td className="text-right font-mono text-sm text-emerald-700">
                {row.completed}
              </td>
              <td className="text-right font-mono text-sm text-rose-700">
                {row.failed + row.scan_failed || "—"}
              </td>
              <td className="text-right font-mono text-sm text-amber-700">
                {row.quarantined || "—"}
              </td>
              <td className="text-right font-mono text-sm text-navy-700">
                {fmt(row.avg_duration_seconds)}
              </td>
              <td className="text-right font-mono text-sm text-rose-700">
                {row.alerts_high || "—"}
              </td>
              <td className="text-right font-mono text-sm text-amber-700">
                {row.alerts_medium || "—"}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
