import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import { queryKeys, type SortState } from "../lib/queryKeys";
import type { Page, RecentTransactionItem } from "../types/api";

export function useRecentTransactions(
  sort: SortState,
  limit: number,
  offset: number,
) {
  const params = new URLSearchParams({
    sort: sort.sort,
    dir: sort.dir,
    limit: String(limit),
    offset: String(offset),
  });
  return useQuery({
    queryKey: queryKeys.recentTransactionsPage(sort, limit, offset),
    queryFn: () =>
      api.get<Page<RecentTransactionItem>>(
        `/ui/oltp/transactions/recent?${params.toString()}`,
      ),
    refetchInterval: 3_000,
    placeholderData: keepPreviousData,
  });
}
