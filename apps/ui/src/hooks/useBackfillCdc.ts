import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { CdcBackfillRequest, CdcBackfillResponse } from "../types/api";

export function useBackfillCdc() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: CdcBackfillRequest) =>
      api.post<CdcBackfillResponse>("/ui/demo/backfill/cdc", vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
