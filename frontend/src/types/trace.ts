export type EventType =
  | "llm_start" | "chat_model_start" | "llm_end" | "llm_new_token" | "llm_error"
  | "chain_start" | "chain_end" | "chain_error"
  | "tool_start" | "tool_end" | "tool_error"
  | "retriever_start" | "retriever_end"
  | "agent_action" | "agent_finish" | "text";

export type TraceStatus = "running" | "succeeded" | "failed";

export interface TraceEvent {
  event_id: string;
  run_id: string;
  parent_run_id: string | null;
  event_type: EventType;
  timestamp: string;
  name?: string | null;
  serialized?: Record<string, unknown> | null;
  inputs?: unknown;
  outputs?: unknown;
  metadata: Record<string, unknown>;
  tags: string[];
  level: string;
  // Middleware 识别
  is_middleware?: boolean;
  middleware_name?: string | null;
  node_name?: string | null;
}

export interface Trace {
  trace_id: string;
  name?: string | null;
  thread_id?: string | null;
  input?: unknown;
  output?: unknown;
  messages: unknown[];
  structured_response?: unknown;
  metadata: Record<string, unknown>;
  tags: string[];
  start_time?: string | null;
  end_time?: string | null;
  duration_ms?: number | null;
  status: TraceStatus;
  error?: { type: string; message: string } | null;
  events: TraceEvent[];
}
