export type StatsDimension = "session" | "user" | "app";

export interface TokenStatsItem {
  key: string;
  label: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface TokenStatsTotals {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  call_count: number;
}

export interface TokenStats {
  dimension: StatsDimension;
  items: TokenStatsItem[];
  totals: TokenStatsTotals;
}

export interface Overview {
  total_traces: number;
  total_tokens: number;
  total_sessions: number;
  avg_tokens_per_trace: number;
  success_rate: number;
}
