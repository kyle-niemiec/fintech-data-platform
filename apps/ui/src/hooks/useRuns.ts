import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { RunSummary } from "../types/api";

export function useRuns(pipelineNames: string[] = []) {
  const query =
    pipelineNames.length > 0
      ? "?" +
        pipelineNames
          .map((n) => `pipeline_name=${encodeURIComponent(n)}`)
          .join("&")
      : "";
  return useQuery({
    queryKey: queryKeys.runsFiltered(pipelineNames),
    queryFn: () => api.get<RunSummary[]>(`/ui/runs${query}`),
    refetchInterval: 5_000,
  });
}
