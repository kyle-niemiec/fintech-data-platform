import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { RunSummary } from "../types/api";

export function useRuns() {
  return useQuery({
    queryKey: queryKeys.runs,
    queryFn: () => api.get<RunSummary[]>("/ui/runs"),
    refetchInterval: 5_000,
  });
}
