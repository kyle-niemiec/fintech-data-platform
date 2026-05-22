import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys, type SortState } from "../lib/queryKeys";
import type { AlertItem, Page } from "../types/api";

const DEFAULT_SORT: SortState = { sort: "occurred", dir: "desc" };

/**
 * Read the alert feed. When `runId` is provided the feed is scoped to that run
 * (backed by the `/ui/alerts?run_id=` filter) with the default order; otherwise
 * the global feed is returned with the caller's `sort`. Polled so new
 * failures/risk events surface without a manual reload.
 */
export function useAlerts(
  runId?: string,
  sort: SortState = DEFAULT_SORT,
  limit = 25,
  offset = 0,
) {
  const params = new URLSearchParams();
  if (runId) params.set("run_id", runId);
  params.set("sort", sort.sort);
  params.set("dir", sort.dir);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return useQuery({
    queryKey: runId
      ? queryKeys.alertsForRun(runId)
      : queryKeys.alertsPage(sort, limit, offset),
    queryFn: () => api.get<Page<AlertItem>>(`/ui/alerts?${params.toString()}`),
    refetchInterval: 3_000,
    placeholderData: keepPreviousData,
  });
}
