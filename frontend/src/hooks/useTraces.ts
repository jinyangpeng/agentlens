import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useTraces(limit = 50, offset = 0, threadId?: string) {
  return useQuery({
    queryKey: ["traces", limit, offset, threadId],
    queryFn: () => api.listTraces(limit, offset, threadId),
  });
}

export function useTrace(traceId: string) {
  return useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => api.getTrace(traceId),
    enabled: !!traceId,
  });
}

export function useThreadTraces(threadId: string) {
  return useQuery({
    queryKey: ["thread", threadId],
    queryFn: () => api.listByThread(threadId),
    enabled: !!threadId,
  });
}

export function useDeleteTrace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTrace(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["traces"] }),
  });
}
