import { Link, useSearchParams } from "react-router-dom";
import PageContainer from "../components/layout/PageContainer";
import RunsTable from "../components/runs/RunsTable";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import PipelineFilterPills from "../components/runs/PipelineFilterPills";
import { useRuns } from "../hooks/useRuns";
import {
  PIPELINE_ORDER,
  pipelineNamesFor,
  type PipelineKind,
} from "../lib/pipelineColors";

const ALLOWED = new Set<PipelineKind>(PIPELINE_ORDER);

export default function RunsPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const selected = searchParams
    .getAll("pipeline")
    .filter((k): k is PipelineKind => ALLOWED.has(k as PipelineKind));

  const toggle = (kind: PipelineKind) => {
    const next = new Set(selected);
    if (next.has(kind)) next.delete(kind);
    else next.add(kind);
    const params = new URLSearchParams(searchParams);
    params.delete("pipeline");
    for (const k of next) params.append("pipeline", k);
    setSearchParams(params, { replace: true });
  };

  const pipelineNames = pipelineNamesFor(selected);
  const { data, isLoading, error, isFetching } = useRuns(pipelineNames);

  return (
    <PageContainer
      title="Pipeline Runs"
      description="Unified view of every pipeline run across sources, polled every 5 seconds. Use the pills to filter by pipeline."
      actions={
        <Link to="/demo/upload" className="btn-primary">
          Trigger Demo Upload
        </Link>
      }
    >
      <div className="mb-4">
        <PipelineFilterPills selected={selected} onToggle={toggle} />
      </div>
      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title={
            selected.length > 0
              ? "No runs match the selected pipelines"
              : "No pipeline runs yet"
          }
          description={
            selected.includes("salesforce") && selected.length === 1
              ? "The Salesforce pipeline ships in Phase 5. No runs will appear here until then."
              : "Trigger a demo upload or wait for the CDC load generator to produce runs."
          }
          action={
            <Link to="/demo/upload" className="btn-primary">
              Go to Demo Upload
            </Link>
          }
        />
      ) : (
        <>
          <RunsTable runs={data} />
          <div className="text-right text-xs text-navy-500">
            {isFetching ? "Refreshing…" : `${data.length} run(s)`}
          </div>
        </>
      )}
    </PageContainer>
  );
}
