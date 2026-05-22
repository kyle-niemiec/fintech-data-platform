import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { api } from "../lib/apiClient";
import type { ConsumerLagItem } from "../types/api";

export function useConsumerLag() {
  return useQuery({
    queryKey: ["metrics", "consumer-lag"],
    queryFn: () => api.get<ConsumerLagItem[]>("/ui/metrics/consumer-lag"),
    retry: false,
    refetchInterval: 3_000,
    placeholderData: keepPreviousData,
  });
}
