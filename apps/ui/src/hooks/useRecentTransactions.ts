import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys } from "../lib/queryKeys";
import type { Page, RecentTransactionItem } from "../types/api";

export function useRecentTransactions(limit: number, offset: number) {
  return useQuery({
    queryKey: queryKeys.recentTransactionsPage(limit, offset),
    queryFn: () =>
      api.get<Page<RecentTransactionItem>>(
        `/ui/oltp/transactions/recent?limit=${limit}&offset=${offset}`,
      ),
    refetchInterval: 3_000,
    placeholderData: keepPreviousData,
  });
}
