import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { RunPreviewResponse } from "../types/api";

// Lazy: only fetched while the Preview tab is open (`enabled`), so preview data
// stays off the wire until requested. The backend re-enforces the gate and
// returns 404 for ineligible runs.
export function usePreview(runId: string, enabled: boolean) {
  return useQuery({
    queryKey: queryKeys.runPreview(runId),
    queryFn: () => api.get<RunPreviewResponse>(`/ui/runs/${runId}/preview`),
    enabled,
    staleTime: Infinity,
  });
}
