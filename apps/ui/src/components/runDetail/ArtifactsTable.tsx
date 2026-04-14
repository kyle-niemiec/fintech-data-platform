import StageBadge from "../common/StageBadge";
import { formatTimestamp } from "../../lib/formatters";
import type { ArtifactTrailItem } from "../../types/api";

export default function ArtifactsTable({
  items,
}: {
  items: ArtifactTrailItem[];
}) {
  if (items.length === 0) {
    return (
      <div className="card card-pad text-sm text-navy-600">
        No artifacts produced yet.
      </div>
    );
  }
  return (
    <div className="card overflow-hidden">
      <table className="table-default">
        <thead className="bg-slate-50">
          <tr>
            <th>Stage</th>
            <th>Role</th>
            <th>Format</th>
            <th>URI</th>
            <th>When</th>
          </tr>
        </thead>
        <tbody>
          {items.map((a, i) => (
            <tr key={`${a.event_id}-${a.artifact_role}-${i}`}>
              <td>
                <StageBadge stage={a.stage} />
              </td>
              <td>
                <span
                  className={`rounded px-1.5 py-0.5 text-[11px] font-semibold uppercase ${
                    a.artifact_role === "input"
                      ? "bg-slate-100 text-slate-700"
                      : "bg-emerald-100 text-emerald-800"
                  }`}
                >
                  {a.artifact_role}
                </span>
              </td>
              <td className="font-mono text-xs">{a.format ?? "—"}</td>
              <td className="break-all font-mono text-xs">{a.uri}</td>
              <td className="whitespace-nowrap text-xs text-navy-600">
                {formatTimestamp(a.occurred_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
