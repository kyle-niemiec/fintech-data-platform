import StatusPill from "../common/StatusPill";
import MonoId from "../common/MonoId";
import { formatDuration, formatTimestamp } from "../../lib/formatters";
import { pipelineDisplayNameFor } from "../../lib/pipelineColors";
import type { RunDetail } from "../../types/api";

function Field({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <div className="text-[11px] font-semibold uppercase tracking-wide text-navy-500">
        {label}
      </div>
      <div className="mt-0.5 text-sm text-navy-900">{children}</div>
    </div>
  );
}

export default function RunSummaryHeader({ run }: { run: RunDetail }) {
  return (
    <div className="card card-pad">
      <div className="flex flex-wrap items-center gap-3">
        <StatusPill status={run.status} />
        <span className="font-mono text-sm text-navy-700">
          {pipelineDisplayNameFor(run.pipeline_name)}
        </span>
        <span className="text-slate-400">·</span>
        <MonoId value={run.run_id} />
      </div>
      <div className="mt-5 grid grid-cols-2 gap-5 md:grid-cols-4">
        <Field label="Source">{run.source_system}</Field>
        <Field label="Trigger">{run.trigger_type}</Field>
        <Field label="Initiator">
          <span className="font-mono text-xs">{run.initiator ?? "—"}</span>
        </Field>
        <Field label="Latest Stage">{run.latest_stage ?? "—"}</Field>
        <Field label="Started">{formatTimestamp(run.started_at)}</Field>
        <Field label="Completed">{formatTimestamp(run.completed_at)}</Field>
        <Field label="Duration">
          {formatDuration(run.started_at, run.completed_at)}
        </Field>
        <Field label="Parent Run">
          {run.parent_run_id ? (
            <MonoId value={run.parent_run_id} short />
          ) : (
            "—"
          )}
        </Field>
      </div>
      <div className="mt-5 rounded border border-slate-200 bg-slate-50 px-3 py-2">
        <div className="text-[11px] font-semibold uppercase tracking-wide text-navy-500">
          Trigger Event Ref
        </div>
        <div className="mt-0.5 break-all font-mono text-xs text-navy-800">
          {run.trigger_event_ref}
        </div>
      </div>
    </div>
  );
}
