export const queryKeys = {
  runs: ["runs"] as const,
  runsFiltered: (pipelineNames: string[]) =>
    ["runs", { pipelineNames: [...pipelineNames].sort() }] as const,
  recentTransactions: ["oltp", "transactions", "recent"] as const,
  run: (runId: string) => ["run", runId] as const,
  runEvents: (runId: string) => ["run", runId, "events"] as const,
  runLineage: (runId: string) => ["run", runId, "lineage"] as const,
  runArtifacts: (runId: string) => ["run", runId, "artifacts"] as const,
};
