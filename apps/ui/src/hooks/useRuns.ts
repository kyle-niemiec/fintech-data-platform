import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys, type SortState } from "../lib/queryKeys";
import type { Page, RunSummary } from "../types/api";

export function useRuns(
  pipelineNames: string[],
  backfill: boolean,
  sort: SortState,
  limit: number,
  offset: number,
) {
  const params = new URLSearchParams();
  for (const name of pipelineNames) params.append("pipeline_name", name);
  if (backfill) params.set("backfill", "true");
  params.set("sort", sort.sort);
  params.set("dir", sort.dir);
  params.set("limit", String(limit));
  params.set("offset", String(offset));
  return useQuery({
    queryKey: queryKeys.runsFiltered(pipelineNames, backfill, sort, limit, offset),
    queryFn: () => api.get<Page<RunSummary>>(`/ui/runs?${params.toString()}`),
    refetchInterval: 3_000,
    placeholderData: keepPreviousData,
  });
}
