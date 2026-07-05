import { useState } from "react";
import { Link } from "react-router-dom";
import { Copy, Check, Clock, Tag, Hash, MessagesSquare, Settings2 } from "lucide-react";
import type { Trace } from "@/types/trace";
import { Badge } from "./ui/Badge";

const STATUS_VARIANT: Record<string, "success" | "failed" | "running"> = {
  succeeded: "success",
  failed: "failed",
  running: "running",
};

interface Props {
  trace: Trace;
}

/** 紧凑单行 Header，节省垂直空间。 */
export default function TraceDetailHeader({ trace }: Props) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(trace.trace_id);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* ignore */
    }
  };

  // 收集 trace 中出现的 middleware 名称（去重）
  const middlewareSet = new Map<string, number>(); // name -> count
  for (const ev of trace.events) {
    if (ev.is_middleware && ev.middleware_name) {
      middlewareSet.set(ev.middleware_name, (middlewareSet.get(ev.middleware_name) ?? 0) + 1);
    }
  }

  return (
    <div className="flex items-center gap-2 flex-wrap text-sm">
      <h1 className="font-semibold text-slate-900 truncate max-w-[280px]">
        {trace.name ?? trace.trace_id.slice(0, 8)}
      </h1>
      <Badge variant={STATUS_VARIANT[trace.status] ?? "neutral"}>{trace.status}</Badge>
      {trace.thread_id && (
        <Link
          to={`/threads/${encodeURIComponent(trace.thread_id)}`}
          className="inline-flex items-center gap-1 text-xs mono px-1.5 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200 hover:bg-indigo-100 transition-colors"
          title="查看会话详情"
        >
          <MessagesSquare className="w-3 h-3" />
          {trace.thread_id}
        </Link>
      )}
      {trace.duration_ms != null && (
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Clock className="w-3.5 h-3.5" />
          <span className="mono font-medium text-slate-700">{trace.duration_ms}ms</span>
        </span>
      )}
      {trace.start_time && (
        <span className="text-xs text-slate-500 mono">
          {new Date(trace.start_time).toLocaleString("zh-CN", { hour12: false })}
        </span>
      )}
      <button
        onClick={copy}
        className="inline-flex items-center gap-1 text-xs mono text-slate-400 hover:text-slate-700 transition-colors ml-auto"
        title="复制 Trace ID"
      >
        <Hash className="w-3 h-3" />
        <span className="truncate max-w-[200px]">{trace.trace_id}</span>
        {copied ? <Check className="w-3 h-3 text-emerald-600" /> : <Copy className="w-3 h-3" />}
      </button>
      {trace.tags.length > 0 && (
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Tag className="w-3 h-3" />
          {trace.tags.map((t, i) => (
            <span key={i} className="mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
              {t}
            </span>
          ))}
        </span>
      )}
      {/* Middleware 徽章列表 */}
      {middlewareSet.size > 0 && (
        <span className="inline-flex items-center gap-1 text-xs text-slate-500">
          <Settings2 className="w-3 h-3 text-orange-600" />
          {Array.from(middlewareSet.entries()).map(([name, count]) => (
            <span
              key={name}
              className="inline-flex items-center gap-1 mono px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200"
              title={`${name} 触发 ${count} 次`}
            >
              {name}
              {count > 1 && <span className="text-orange-500">×{count}</span>}
            </span>
          ))}
        </span>
      )}
      {trace.error && (
        <div className="w-full mt-1.5 rounded border border-red-200 bg-red-50 px-2.5 py-1.5 text-xs text-red-700">
          <span className="font-mono font-medium">{trace.error.type}:</span>{" "}
          {trace.error.message}
        </div>
      )}
    </div>
  );
}
