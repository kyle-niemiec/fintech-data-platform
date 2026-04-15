import { useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { RecentTransactionItem } from "../types/api";

export function useRecentTransactions() {
  return useQuery({
    queryKey: queryKeys.recentTransactions,
    queryFn: () =>
      api.get<RecentTransactionItem[]>("/ui/oltp/transactions/recent"),
    refetchInterval: 5_000,
  });
}
