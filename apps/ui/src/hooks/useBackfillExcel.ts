import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { ExcelBackfillRequest, ExcelBackfillResponse } from "../types/api";

export function useBackfillExcel() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (vars: ExcelBackfillRequest) =>
      api.post<ExcelBackfillResponse>("/ui/demo/backfill/excel", vars),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
