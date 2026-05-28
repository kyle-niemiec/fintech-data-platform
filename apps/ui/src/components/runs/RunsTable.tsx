import { useNavigate } from "react-router-dom";
import StatusPill from "../common/StatusPill";
import MonoId from "../common/MonoId";
import RelativeTime from "../common/RelativeTime";
import SortableHeader from "../common/SortableHeader";
import PipelineBadge from "./PipelineBadge";
import { formatDuration } from "../../lib/formatters";
import { pipelineDisplayNameFor } from "../../lib/pipelineColors";
import type { SortDir, SortState } from "../../lib/queryKeys";
import type { RunSummary } from "../../types/api";

interface Props {
  runs: RunSummary[];
  sort: SortState;
  onSort: (column: string, dir: SortDir) => void;
}

export default function RunsTable({ runs, sort, onSort }: Props) {
  const navigate = useNavigate();
  const th = (column: string, label: string, initialDir: SortDir) => (
    <SortableHeader
      column={column}
      label={label}
      active={sort.sort === column}
      dir={sort.dir}
      onSort={onSort}
      initialDir={initialDir}
    />
  );
  return (
    <div className="card overflow-x-auto">
      <table className="table-default">
        <thead className="bg-slate-50">
          <tr>
            {th("run_id", "Run", "asc")}
            {th("pipeline", "Pipeline", "asc")}
            <th>Source</th>
            {th("status", "Status", "asc")}
            <th>Latest Stage</th>
            {th("started", "Started", "desc")}
            {th("duration", "Duration", "desc")}
          </tr>
        </thead>
        <tbody>
          {runs.map((r) => (
            <tr
              key={r.run_id}
              onClick={() => navigate(`/runs/${r.run_id}`)}
              className="cursor-pointer"
            >
              <td>
                <MonoId value={r.run_id} short />
              </td>
              <td>
                <div className="flex items-center gap-2">
                  <PipelineBadge pipelineName={r.pipeline_name} />
                  <div>
                    <div className="flex items-center gap-1.5 font-medium">
                      {pipelineDisplayNameFor(r.pipeline_name)}
                      {r.is_backfill && (
                        <span className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide bg-violet-100 text-violet-800">
                          Backfill
                        </span>
                      )}
                    </div>
                    <div className="text-xs text-navy-500">{r.pipeline_class}</div>
                  </div>
                </div>
              </td>
              <td className="font-mono text-xs">{r.source_system}</td>
              <td>
                <StatusPill status={r.status} />
              </td>
              <td className="font-mono text-xs text-navy-700">
                {r.latest_stage ?? "—"}
              </td>
              <td>
                <RelativeTime iso={r.started_at} />
              </td>
              <td className="text-navy-700">
                {formatDuration(r.started_at, r.completed_at)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
