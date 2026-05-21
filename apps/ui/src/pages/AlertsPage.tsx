import PageContainer from "../components/layout/PageContainer";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import AlertsTable from "../components/alerts/AlertsTable";
import { useAlerts } from "../hooks/useAlerts";

export default function AlertsPage() {
  const { data, isLoading, error, isFetching } = useAlerts();

  return (
    <PageContainer
      title="Alerts"
      description="Failure and risk events raised across every pipeline (scan rejections, schema quarantines, high-risk fraud flags, and pipeline failures). Newest first; polled every 5 seconds. Select a row to open its run."
    >
      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.length === 0 ? (
        <EmptyState
          title="No alerts"
          description="Nothing has been flagged yet. Quarantined uploads and high-risk transactions will appear here."
        />
      ) : (
        <>
          <AlertsTable alerts={data} />
          <div className="text-right text-xs text-navy-500">
            {isFetching ? "Refreshing…" : `${data.length} alert(s)`}
          </div>
        </>
      )}
    </PageContainer>
  );
}
