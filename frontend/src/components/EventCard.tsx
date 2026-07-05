import { useMemo } from "react";
import type { TraceEvent } from "@/types/trace";
import { Badge } from "./ui/Badge";
import JsonViewer from "./JsonViewer";
import { Settings2, Hash, Layers, GitBranch } from "lucide-react";

const TYPE_VARIANT: Record<string, "info" | "success" | "failed" | "neutral"> = {
  llm_start: "info",
  chat_model_start: "info",
  llm_end: "info",
  chain_start: "success",
  chain_end: "success",
  tool_start: "neutral",
  tool_end: "neutral",
  agent_action: "info",
  agent_finish: "info",
  retriever_start: "info",
  retriever_end: "info",
  text: "neutral",
};
const ERROR_TYPES = new Set(["llm_error", "chain_error", "tool_error"]);

interface Props {
  event: TraceEvent;
  depth: number;
  /** 全局序号（来自父组件排序后） */
  index?: number;
  /** 来源 trace 序号（多 trace 会话场景） */
  sourceIndex?: number;
  /** 来源 trace 名称（多 trace 会话场景） */
  sourceName?: string;
}

export default function EventCard({ event, depth, index, sourceIndex, sourceName }: Props) {
  const isError = ERROR_TYPES.has(event.event_type);
  const variant = isError ? "failed" : TYPE_VARIANT[event.event_type] ?? "neutral";

  // 中间件行为摘要：基于 inputs / outputs 自动推断
  const behaviorHint = useMemo(() => getBehaviorHint(event), [event]);

  return (
    <div
      className={`rounded-lg border bg-white px-3.5 py-2.5 shadow-[0_1px_2px_rgba(15,23,42,0.04)] hover:shadow-[0_1px_3px_rgba(15,23,42,0.08)] transition-all ${
        event.is_middleware
          ? "border-orange-300 hover:border-orange-400"
          : "border-slate-200 hover:border-slate-300"
      }`}
      style={{ marginLeft: depth * 28 }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        {/* 全局序号 */}
        {typeof index === "number" && (
          <span className="inline-flex items-center gap-0.5 text-[10px] mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
            <Hash className="w-2.5 h-2.5" />
            {index + 1}
          </span>
        )}
        <Badge variant={variant} className="mono">
          {event.event_type}
        </Badge>
        {event.is_middleware && (
          <span className="inline-flex items-center gap-1 text-[10px] mono px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200">
            <Settings2 className="w-3 h-3" />
            {event.middleware_name || "Middleware"}
          </span>
        )}
        {event.name && (
          <span className="text-sm font-semibold text-slate-800">{event.name}</span>
        )}
        {event.node_name && !event.is_middleware && (
          <span className="text-[10px] mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
            {event.node_name}
          </span>
        )}
        {/* 来源 trace（多 trace 会话场景） */}
        {typeof sourceIndex === "number" && sourceName && (
          <span className="inline-flex items-center gap-1 text-[10px] mono px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
            <Layers className="w-2.5 h-2.5" />
            调用 #{sourceIndex + 1} · {sourceName}
          </span>
        )}
        {/* 中间件行为摘要 */}
        {behaviorHint && (
          <span className="inline-flex items-center gap-1 text-[10px] mono px-1.5 py-0.5 rounded bg-purple-50 text-purple-700 border border-purple-200">
            <GitBranch className="w-2.5 h-2.5" />
            {behaviorHint}
          </span>
        )}
        <span className="text-[11px] text-slate-400 ml-auto mono">
          {new Date(event.timestamp).toLocaleString("zh-CN", { hour12: false })}
        </span>
      </div>
      {(event.inputs !== undefined && event.inputs !== null && !isEmpty(event.inputs)) ||
      (event.outputs !== undefined && event.outputs !== null && !isEmpty(event.outputs)) ? (
        <div className="mt-2 space-y-1.5">
          {event.inputs !== undefined && event.inputs !== null && !isEmpty(event.inputs) && (
            <JsonViewer data={event.inputs} label="输入" />
          )}
          {event.outputs !== undefined && event.outputs !== null && !isEmpty(event.outputs) && (
            <JsonViewer data={event.outputs} label="输出" />
          )}
        </div>
      ) : null}
      {event.tags.length > 0 && (
        <div className="flex gap-1 flex-wrap mt-2">
          {event.tags.map((t, i) => (
            <span key={i} className="text-[10px] mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
              #{t}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

// ---- 中间件行为摘要 ----

function summarizeMessages(messages: unknown): { count: number; chars: number } | null {
  if (!Array.isArray(messages)) return null;
  let chars = 0;
  for (const m of messages) {
    const c = (m as { content?: unknown })?.content;
    if (typeof c === "string") chars += c.length;
    else if (c != null) chars += JSON.stringify(c).length;
  }
  return { count: messages.length, chars };
}

function getBehaviorHint(event: TraceEvent): string | null {
  if (!event.is_middleware || !event.middleware_name) return null;
  const name = event.middleware_name;
  // 仅对 chain_start / chain_end 计算
  if (event.event_type === "chain_start") {
    // PII: 统计输入里可能存在的 PII 模式（粗略）
    if (name.includes("PII")) {
      const ins = event.inputs as { messages?: unknown } | undefined;
      const text = JSON.stringify(event.inputs ?? {});
      const email = (text.match(/[\w.-]+@[\w.-]+/g) || []).length;
      const phone = (text.match(/\b1[3-9]\d{9}\b/g) || []).length;
      const idCard = (text.match(/\b\d{17}[\dXx]\b/g) || []).length;
      const total = email + phone + idCard;
      if (total > 0) {
        const parts: string[] = [];
        if (email) parts.push(`邮箱×${email}`);
        if (phone) parts.push(`手机×${phone}`);
        if (idCard) parts.push(`身份证×${idCard}`);
        return `检测到 ${parts.join("、")}`;
      }
      return "扫描中（未发现 PII）";
    }
    // Summarization: 显示当前历史长度
    if (name.includes("Summarization")) {
      const ins = event.inputs as { messages?: unknown } | undefined;
      const s = summarizeMessages(ins?.messages);
      if (s) return `历史 ${s.count} 条 / ${s.chars} 字符`;
      return null;
    }
  }
  if (event.event_type === "chain_end") {
    // PII: 检测输出中是否被脱敏（[REDACTED_*]）
    if (name.includes("PII")) {
      const text = JSON.stringify(event.outputs ?? {});
      const redacted = (text.match(/\[REDACTED_[A-Z_]+\]/g) || []).length;
      if (redacted > 0) return `脱敏 ${redacted} 处`;
      return "未脱敏";
    }
    // Summarization: 压缩前后对比
    if (name.includes("Summarization")) {
      // 找同 run 的 start（从前一个事件推断）
      // 这里 inputs 不在手，但用 outputs 推断即可
      const s = summarizeMessages((event.outputs as { messages?: unknown } | undefined)?.messages);
      if (s) return `压缩后 ${s.count} 条 / ${s.chars} 字符`;
    }
  }
  return null;
}

function isEmpty(v: unknown): boolean {
  if (v === null || v === undefined) return true;
  if (typeof v === "string") return v === "" || v === "{}" || v === "[]";
  if (typeof v === "object") return Object.keys(v as object).length === 0;
  return false;
}
