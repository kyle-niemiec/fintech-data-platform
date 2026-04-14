import { Link } from "react-router-dom";
import PageContainer from "../components/layout/PageContainer";
import RunsTable from "../components/runs/RunsTable";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import { useRuns } from "../hooks/useRuns";

export default function RunsPage() {
  const { data, isLoading, error, isFetching } = useRuns();

  return (
    <PageContainer
      title="Pipeline Runs"
      description="Live view of every pipeline run, polled every 5 seconds. Click a row to inspect events, lineage, and artifacts."
      actions={
        <Link to="/demo/upload" className="btn-primary">
          Trigger Demo Upload
        </Link>
      }
    >
      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="No pipeline runs yet"
          description="Trigger a demo upload to kick off the Excel pipeline — the first run will appear here within a few seconds."
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
