import { useState } from "react";
import PageContainer from "../components/layout/PageContainer";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import AlertsTable from "../components/alerts/AlertsTable";
import Pagination from "../components/common/Pagination";
import { useAlerts } from "../hooks/useAlerts";

const DEFAULT_PAGE_SIZE = 25;

export default function AlertsPage() {
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [page, setPage] = useState(1);
  const { data, isLoading, error } = useAlerts(
    undefined,
    pageSize,
    (page - 1) * pageSize,
  );

  return (
    <PageContainer
      title="Alerts"
      description="Failure and risk events raised across every pipeline (scan rejections, schema quarantines, high-risk fraud flags, and pipeline failures). Newest first; polled every 3 seconds. Select a row to open its run."
    >
      {error ? (
        <ErrorBanner message={(error as Error).message} />
      ) : isLoading ? (
        <LoadingSkeleton rows={6} />
      ) : !data || data.total === 0 ? (
        <EmptyState
          title="No alerts"
          description="Nothing has been flagged yet. Quarantined uploads and high-risk transactions will appear here."
        />
      ) : (
        <>
          <AlertsTable alerts={data.items} />
          <Pagination
            page={page}
            pageSize={pageSize}
            total={data.total}
            onPageChange={setPage}
            onPageSizeChange={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        </>
      )}
    </PageContainer>
  );
}
