import type { TraceEvent } from "@/types/trace";
import { Boxes, Cpu, Wrench, Search, Bot, FileText } from "lucide-react";

/** 聚合后的 run 节点：合并同 run_id 的 start/end 事件 */
export interface RunNode {
  run_id: string;
  parent_run_id: string | null;
  kind: "chain" | "llm" | "tool" | "retriever" | "agent" | "text";
  name: string;
  className: string; // 从 serialized.id 提取的真实类名
  start_time: string | null;
  end_time: string | null;
  duration_ms: number | null;
  status: "succeeded" | "failed" | "running";
  inputs?: unknown;
  outputs?: unknown;
  inputSummary: string;
  outputSummary: string;
  error?: { type: string; message: string };
  children: RunNode[];
  is_middleware: boolean;
  middleware_name: string | null;
  node_name: string | null;
}

export const KIND_META: Record<
  RunNode["kind"],
  { label: string; icon: React.ComponentType<{ className?: string }>; color: string; bg: string; border: string }
> = {
  chain: { label: "Chain", icon: Boxes, color: "text-indigo-600", bg: "bg-indigo-50", border: "border-indigo-300" },
  llm: { label: "LLM", icon: Cpu, color: "text-violet-600", bg: "bg-violet-50", border: "border-violet-300" },
  tool: { label: "Tool", icon: Wrench, color: "text-amber-600", bg: "bg-amber-50", border: "border-amber-300" },
  retriever: { label: "Retriever", icon: Search, color: "text-cyan-600", bg: "bg-cyan-50", border: "border-cyan-300" },
  agent: { label: "Agent", icon: Bot, color: "text-emerald-600", bg: "bg-emerald-50", border: "border-emerald-300" },
  text: { label: "Text", icon: FileText, color: "text-slate-600", bg: "bg-slate-50", border: "border-slate-300" },
};

export function classifyEvent(t: string): RunNode["kind"] | null {
  if (t.startsWith("chain")) return "chain";
  if (t.startsWith("llm") || t.startsWith("chat_model")) return "llm";
  if (t.startsWith("tool")) return "tool";
  if (t.startsWith("retriever")) return "retriever";
  if (t.startsWith("agent")) return "agent";
  if (t === "text") return "text";
  return null;
}

export function extractClassName(serialized: unknown, fallback: string): string {
  if (!serialized || typeof serialized !== "object") return fallback;
  const s = serialized as Record<string, unknown>;
  const id = s.id;
  if (Array.isArray(id) && id.length > 0) return String(id[id.length - 1]);
  if (typeof s.name === "string" && s.name) return s.name;
  return fallback;
}

function truncate(s: string, n: number): string {
  const t = s.replace(/\s+/g, " ").trim();
  return t.length > n ? t.slice(0, n) + "…" : t;
}

function summarizeInput(kind: RunNode["kind"], inputs: unknown): string {
  if (inputs == null) return "";
  if (typeof inputs === "string") return truncate(inputs, 80);
  const obj = inputs as Record<string, unknown>;
  if (kind === "chain") {
    if (typeof obj.input === "string") return truncate(obj.input, 80);
    if (typeof obj.input === "object" && obj.input !== null) {
      return summarizeInput("llm", obj.input);
    }
  }
  if (kind === "llm") {
    const msgs = obj.messages;
    if (Array.isArray(msgs)) {
      const flat = Array.isArray(msgs[0]) ? (msgs[0] as unknown[]) : msgs;
      const last = flat[flat.length - 1] as Record<string, unknown> | undefined;
      if (last) {
        const content = last.content;
        if (typeof content === "string") return truncate(content, 80);
        if (Array.isArray(content)) {
          const textPart = content.find(
            (c) => typeof c === "object" && c !== null && (c as Record<string, unknown>).type === "text"
          ) as Record<string, unknown> | undefined;
          if (textPart && typeof textPart.text === "string") return truncate(textPart.text, 80);
        }
      }
    }
    if (Array.isArray(obj.prompts) && obj.prompts.length > 0) {
      return truncate(String(obj.prompts[obj.prompts.length - 1]), 80);
    }
  }
  if (kind === "tool" && typeof obj.input === "string") {
    return truncate(obj.input, 80);
  }
  if (kind === "retriever" && typeof obj.query === "string") {
    return truncate(obj.query, 80);
  }
  if (kind === "agent") {
    if (typeof obj.tool === "string" && obj.tool_input != null) {
      return `${obj.tool}(${truncate(JSON.stringify(obj.tool_input), 50)})`;
    }
  }
  try {
    const j = JSON.stringify(inputs);
    if (j && j !== "{}" && j !== "[]") return truncate(j, 80);
  } catch {
    /* ignore */
  }
  return "";
}

function summarizeOutput(kind: RunNode["kind"], outputs: unknown): string {
  if (outputs == null) return "";
  if (typeof outputs === "string") return truncate(outputs, 80);
  const obj = outputs as Record<string, unknown>;
  if (kind === "llm") {
    const gens = obj.generations;
    if (Array.isArray(gens) && Array.isArray(gens[0]) && gens[0].length > 0) {
      const gen = (gens[0] as unknown[])[0] as Record<string, unknown>;
      const text = gen.text;
      if (typeof text === "string" && text) return truncate(text, 80);
      const msg = gen.message as Record<string, unknown> | undefined;
      if (msg && typeof msg.content === "string") return truncate(msg.content, 80);
      const tc = msg?.tool_calls;
      if (Array.isArray(tc) && tc.length > 0) {
        const first = tc[0] as Record<string, unknown>;
        if (typeof first.name === "string") {
          const args = first.args ? truncate(JSON.stringify(first.args), 40) : "";
          return `→ 调用 ${first.name}(${args})`;
        }
      }
    }
  }
  if (kind === "tool" && typeof outputs === "string") return truncate(outputs, 80);
  if (kind === "chain" && typeof obj.output === "string") return truncate(obj.output, 80);
  if (kind === "agent") {
    const rv = obj.return_values;
    if (rv && typeof rv === "object") {
      const o = (rv as Record<string, unknown>).output;
      if (typeof o === "string") return truncate(o, 80);
    }
  }
  try {
    const j = JSON.stringify(outputs);
    if (j && j !== "{}" && j !== "[]") return truncate(j, 80);
  } catch {
    /* ignore */
  }
  return "";
}

/** 把 events 聚合为 RunNode 森林（多棵树，每棵 root.run_id 唯一） */
export function buildRunTree(events: TraceEvent[]): RunNode[] {
  const byRun = new Map<string, TraceEvent[]>();
  for (const e of events) {
    if (!byRun.has(e.run_id)) byRun.set(e.run_id, []);
    byRun.get(e.run_id)!.push(e);
  }

  const nodes = new Map<string, RunNode>();
  for (const [runId, evs] of byRun.entries()) {
    const sorted = [...evs].sort(
      (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
    );
    const startEv = sorted.find((e) => e.event_type.endsWith("_start")) ?? sorted[0];
    const endEv = sorted.find((e) => e.event_type.endsWith("_end"));
    const errEv = sorted.find((e) => e.event_type.endsWith("_error"));
    const kind = classifyEvent(startEv.event_type) ?? "text";
    const fallbackName = startEv.name ?? "";
    const className = extractClassName(startEv.serialized, fallbackName);

    const startT = startEv ? new Date(startEv.timestamp).getTime() : null;
    const endT = endEv ? new Date(endEv.timestamp).getTime() : null;
    const dur = startT && endT ? endT - startT : null;

    const inputs = startEv?.inputs;
    const outputs = endEv?.outputs;

    nodes.set(runId, {
      run_id: runId,
      parent_run_id: startEv.parent_run_id,
      kind,
      name: fallbackName,
      className,
      start_time: startEv?.timestamp ?? null,
      end_time: endEv?.timestamp ?? null,
      duration_ms: dur,
      status: errEv ? "failed" : endEv ? "succeeded" : "running",
      inputs,
      outputs,
      inputSummary: summarizeInput(kind, inputs),
      outputSummary: summarizeOutput(kind, outputs),
      error: errEv ? { type: errEv.event_type, message: String(errEv.outputs ?? "") } : undefined,
      children: [],
      is_middleware: !!startEv?.is_middleware || !!endEv?.is_middleware,
      middleware_name: (startEv?.middleware_name ?? endEv?.middleware_name ?? null) as string | null,
      node_name: (startEv?.node_name ?? endEv?.node_name ?? null) as string | null,
    });
  }

  const roots: RunNode[] = [];
  for (const node of nodes.values()) {
    if (node.parent_run_id && nodes.has(node.parent_run_id)) {
      nodes.get(node.parent_run_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

export function fmtDuration(ms: number | null): string {
  if (ms == null) return "";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

export function shortId(id: string): string {
  return id.slice(0, 8);
}

export function isEmpty(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v === "" || v === "{}" || v === "[]";
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}
