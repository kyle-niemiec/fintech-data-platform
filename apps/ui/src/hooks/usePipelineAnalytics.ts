import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import type { PipelineAnalyticsItem } from "../types/api";

export function usePipelineAnalytics() {
  return useQuery({
    queryKey: ["metrics", "pipeline-analytics"],
    queryFn: () => api.get<PipelineAnalyticsItem[]>("/ui/metrics/pipeline-analytics"),
    refetchInterval: 3_000,
  });
}
