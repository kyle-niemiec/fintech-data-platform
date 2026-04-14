import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import {
  TERMINAL_STATUSES,
  type ArtifactTrailItem,
  type LineageTrailItem,
  type RunDetail,
  type RunEventItem,
} from "../types/api";

const POLL_MS = 3_000;

function pollWhileRunning<T extends { status?: string } | undefined>(
  data: T,
): number | false {
  if (!data?.status) return POLL_MS;
  return TERMINAL_STATUSES.has(data.status) ? false : POLL_MS;
}

export function useRun(runId: string) {
  const run = useQuery({
    queryKey: queryKeys.run(runId),
    queryFn: () => api.get<RunDetail>(`/ui/runs/${runId}`),
    refetchInterval: (q) => pollWhileRunning(q.state.data),
  });

  const active = run.data ? !TERMINAL_STATUSES.has(run.data.status) : true;
  const childInterval = active ? POLL_MS : false;

  const events = useQuery({
    queryKey: queryKeys.runEvents(runId),
    queryFn: () => api.get<RunEventItem[]>(`/ui/runs/${runId}/events`),
    refetchInterval: childInterval,
  });

  const lineage = useQuery({
    queryKey: queryKeys.runLineage(runId),
    queryFn: () => api.get<LineageTrailItem[]>(`/ui/runs/${runId}/lineage`),
    refetchInterval: childInterval,
  });

  const artifacts = useQuery({
    queryKey: queryKeys.runArtifacts(runId),
    queryFn: () => api.get<ArtifactTrailItem[]>(`/ui/runs/${runId}/artifacts`),
    refetchInterval: childInterval,
  });

  return { run, events, lineage, artifacts };
}
