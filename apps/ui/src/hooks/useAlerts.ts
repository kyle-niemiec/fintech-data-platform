import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { AlertItem, Page } from "../types/api";

/**
 * Read the alert feed. When `runId` is provided the feed is scoped to that run
 * (backed by the `/ui/alerts?run_id=` filter); otherwise the global feed is
 * returned. Polled so new failures/risk events surface without a manual reload.
 */
export function useAlerts(runId?: string, limit = 25, offset = 0) {
  const params = new URLSearchParams();
  if (runId) params.set("run_id", runId);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return useQuery({
    queryKey: runId
      ? queryKeys.alertsForRun(runId)
      : queryKeys.alertsPage(limit, offset),
    queryFn: () => api.get<Page<AlertItem>>(`/ui/alerts?${params.toString()}`),
    refetchInterval: 3_000,
    placeholderData: keepPreviousData,
  });
}
