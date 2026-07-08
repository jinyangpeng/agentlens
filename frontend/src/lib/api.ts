import type { Trace } from "@/types/trace";
import type { Overview, StatsDimension, TokenStats } from "@/types/stats";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${await resp.text()}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  listTraces: (limit = 50, offset = 0, threadId?: string) => {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (threadId) params.set("thread_id", threadId);
    return request<Trace[]>(`/traces?${params.toString()}`);
  },
  getTrace: (id: string) => request<Trace>(`/traces/${id}`),
  listByThread: (threadId: string) =>
    request<Trace[]>(`/traces/by_thread/${encodeURIComponent(threadId)}`),
  deleteTrace: (id: string) =>
    request<void>(`/traces/${id}`, { method: "DELETE" }),
  countTraces: () => request<{ count: number }>(`/traces/count/total`),
  getOverview: () => request<Overview>(`/stats/overview`),
  getTokenStats: (
    dimension: StatsDimension,
    startDate?: string,
    endDate?: string
  ) => {
    const params = new URLSearchParams({ dimension });
    if (startDate) params.set("start_date", startDate);
    if (endDate) params.set("end_date", endDate);
    return request<TokenStats>(`/stats/tokens?${params.toString()}`);
  },
};
