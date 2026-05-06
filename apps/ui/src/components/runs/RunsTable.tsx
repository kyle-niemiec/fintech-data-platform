import { useNavigate } from "react-router-dom";
import StatusPill from "../common/StatusPill";
import MonoId from "../common/MonoId";
import RelativeTime from "../common/RelativeTime";
import PipelineBadge from "./PipelineBadge";
import { formatDuration } from "../../lib/formatters";
import { pipelineDisplayNameFor } from "../../lib/pipelineColors";
import type { RunSummary } from "../../types/api";

export default function RunsTable({ runs }: { runs: RunSummary[] }) {
  const navigate = useNavigate();
  return (
    <div className="card overflow-hidden">
      <table className="table-default">
        <thead className="bg-slate-50">
          <tr>
            <th>Run</th>
            <th>Pipeline</th>
            <th>Source</th>
            <th>Status</th>
            <th>Latest Stage</th>
            <th>Started</th>
            <th>Duration</th>
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
                    <div className="font-medium">
                      {pipelineDisplayNameFor(r.pipeline_name)}
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
