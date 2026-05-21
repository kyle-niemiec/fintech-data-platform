import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { CdcTransactionResponse } from "../types/api";

/**
 * Inject one synthetic OLTP transaction. `highRisk` requests the fraud shape
 * (AAPL > $10k) so the CDC fraud path raises a high-severity alert; otherwise a
 * normal transaction is created. Both invalidate the recent-transactions and
 * runs queries so the UI reflects the new row and resulting run.
 */
export function useCreateCdcTransaction() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (highRisk: boolean) =>
      api.post<CdcTransactionResponse>("/ui/demo/oltp/transaction", {
        high_risk: highRisk,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: queryKeys.recentTransactions });
      qc.invalidateQueries({ queryKey: queryKeys.runs });
    },
  });
}
