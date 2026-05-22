import { useState } from "react";
import PageContainer from "../components/layout/PageContainer";
import EmptyState from "../components/common/EmptyState";
import LoadingSkeleton from "../components/common/LoadingSkeleton";
import ErrorBanner from "../components/common/ErrorBanner";
import AlertsTable from "../components/alerts/AlertsTable";
import Pagination from "../components/common/Pagination";
import BusinessStory from "../components/common/BusinessStory";
import { useAlerts } from "../hooks/useAlerts";
import { businessStories } from "../lib/businessStories";
import type { SortDir, SortState } from "../lib/queryKeys";

const DEFAULT_PAGE_SIZE = 10;

export default function AlertsPage() {
  const [pageSize, setPageSize] = useState(DEFAULT_PAGE_SIZE);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState>({ sort: "occurred", dir: "desc" });
  const { data, isLoading, error } = useAlerts(
    undefined,
    sort,
    pageSize,
    (page - 1) * pageSize,
  );

  const onSort = (column: string, dir: SortDir) => {
    setSort({ sort: column, dir });
    setPage(1);
  };

  return (
    <PageContainer
      title="Alerts"
      description="Failure and risk events raised across every pipeline (scan rejections, schema quarantines, high-risk fraud flags, and pipeline failures). Select a row to open its run."
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
          <AlertsTable alerts={data.items} sort={sort} onSort={onSort} />
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
      <BusinessStory {...businessStories.alerts} />
    </PageContainer>
  );
}
