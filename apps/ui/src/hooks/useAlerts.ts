import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { AlertItem } from "../types/api";

/**
 * Read the alert feed. When `runId` is provided the feed is scoped to that run
 * (backed by the `/ui/alerts?run_id=` filter); otherwise the global feed is
 * returned. Polled so new failures/risk events surface without a manual reload.
 */
export function useAlerts(runId?: string) {
  return useQuery({
    queryKey: runId ? queryKeys.alertsForRun(runId) : queryKeys.alerts,
    queryFn: () =>
      api.get<AlertItem[]>(
        runId ? `/ui/alerts?run_id=${encodeURIComponent(runId)}` : "/ui/alerts",
      ),
    refetchInterval: 5_000,
  });
}
