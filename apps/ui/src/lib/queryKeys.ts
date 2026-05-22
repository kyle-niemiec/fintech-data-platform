export const PAGE_SIZE_OPTIONS = [25, 50, 100] as const;

export type SortDir = "asc" | "desc";

export interface SortState {
  sort: string;
  dir: SortDir;
}

export const queryKeys = {
  runs: ["runs"] as const,
  runsFiltered: (
    pipelineNames: string[],
    backfill: boolean,
    sort: SortState,
    limit: number,
    offset: number,
  ) =>
    [
      "runs",
      { pipelineNames: [...pipelineNames].sort(), backfill, sort, limit, offset },
    ] as const,
  recentTransactions: ["oltp", "transactions", "recent"] as const,
  recentTransactionsPage: (sort: SortState, limit: number, offset: number) =>
    ["oltp", "transactions", "recent", { sort, limit, offset }] as const,
  run: (runId: string) => ["run", runId] as const,
  runEvents: (runId: string) => ["run", runId, "events"] as const,
  runLineage: (runId: string) => ["run", runId, "lineage"] as const,
  runArtifacts: (runId: string) => ["run", runId, "artifacts"] as const,
  runPreview: (runId: string) => ["run", runId, "preview"] as const,
  alerts: ["alerts"] as const,
  alertsPage: (sort: SortState, limit: number, offset: number) =>
    ["alerts", { sort, limit, offset }] as const,
  alertsForRun: (runId: string) => ["alerts", runId] as const,
};
