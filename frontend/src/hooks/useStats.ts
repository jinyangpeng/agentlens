import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { StatsDimension } from "@/types/stats";

export function useOverview() {
  return useQuery({
    queryKey: ["stats", "overview"],
    queryFn: () => api.getOverview(),
  });
}

export function useTokenStats(
  dimension: StatsDimension,
  startDate?: string,
  endDate?: string
) {
  return useQuery({
    queryKey: ["stats", "tokens", dimension, startDate, endDate],
    queryFn: () => api.getTokenStats(dimension, startDate, endDate),
  });
}
