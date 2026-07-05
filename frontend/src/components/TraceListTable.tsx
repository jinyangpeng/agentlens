import { useState } from "react";
import { Link } from "react-router-dom";
import {
  Trash2, ChevronRight, Inbox,
  MessagesSquare, Layers, List,
} from "lucide-react";
import type { Trace } from "@/types/trace";
import { useDeleteTrace } from "@/hooks/useTraces";
import { Badge } from "./ui/Badge";

const STATUS_VARIANT: Record<string, "success" | "failed" | "running"> = {
  succeeded: "success",
  failed: "failed",
  running: "running",
};

interface ThreadGroup {
  thread_id: string;
  traces: Trace[];
  latest: Trace;
  start_time: string | null;
  end_time: string | null;
}

function groupByThread(traces: Trace[]): {
  threads: ThreadGroup[];
  standalone: Trace[];
} {
  const map = new Map<string, Trace[]>();
  const standalone: Trace[] = [];
  for (const t of traces) {
    if (t.thread_id) {
      if (!map.has(t.thread_id)) map.set(t.thread_id, []);
      map.get(t.thread_id)!.push(t);
    } else {
      standalone.push(t);
    }
  }
  const threads: ThreadGroup[] = [];
  for (const [thread_id, ts] of map.entries()) {
    // 按 start_time 倒序，最新的在前
    const sorted = [...ts].sort(
      (a, b) =>
        new Date(b.start_time ?? 0).getTime() - new Date(a.start_time ?? 0).getTime()
    );
    const latest = sorted[0];
    const times = ts
      .map((t) => t.start_time)
      .filter((x): x is string => !!x)
      .sort();
    threads.push({
      thread_id,
      traces: sorted,
      latest,
      start_time: times[0] ?? null,
      end_time: times[times.length - 1] ?? null,
    });
  }
  // 会话按最新活动时间倒序
  threads.sort(
    (a, b) =>
      new Date(b.latest.start_time ?? 0).getTime() -
      new Date(a.latest.start_time ?? 0).getTime()
  );
  return { threads, standalone };
}

function fmtRange(start?: string | null, end?: string | null): string {
  const s = start ? new Date(start) : null;
  const e = end ? new Date(end) : null;
  const fmt = (d: Date) =>
    d.toLocaleString("zh-CN", { hour12: false, month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit" });
  if (s && e) return `${fmt(s)} → ${fmt(e)}`;
  if (s) return fmt(s);
  return "—";
}

function TraceRow({ t, showThread = false }: { t: Trace; showThread?: boolean }) {
  const del = useDeleteTrace();
  return (
    <tr className="border-t border-slate-100 hover:bg-slate-50/60 transition-colors group">
      <td className="px-4 py-2.5">
        <Link
          to={`/traces/${t.trace_id}`}
          className="font-medium text-slate-800 hover:text-indigo-600 transition-colors"
        >
          {t.name ?? t.trace_id.slice(0, 8)}
        </Link>
      </td>
      {showThread && (
        <td className="px-4 py-2.5">
          {t.thread_id && (
            <Link
              to={`/?thread_id=${encodeURIComponent(t.thread_id)}`}
              className="text-xs mono text-indigo-600 hover:underline"
            >
              {t.thread_id}
            </Link>
          )}
        </td>
      )}
      <td className="px-4 py-2.5">
        <Badge variant={STATUS_VARIANT[t.status] ?? "neutral"}>{t.status}</Badge>
      </td>
      <td className="px-4 py-2.5 text-slate-600 mono">{t.events.length}</td>
      <td className="px-4 py-2.5 text-slate-600 mono">
        {t.duration_ms != null ? `${t.duration_ms} ms` : "—"}
      </td>
      <td className="px-4 py-2.5 text-slate-500 text-xs mono">
        {t.start_time
          ? new Date(t.start_time).toLocaleString("zh-CN", { hour12: false })
          : "—"}
      </td>
      <td className="px-4 py-2.5">
        <div className="inline-flex gap-0.5 opacity-0 group-hover:opacity-100 transition-opacity">
          <button
            onClick={() => del.mutate(t.trace_id)}
            className="p-1.5 text-slate-400 hover:text-red-600 rounded hover:bg-red-50 transition-colors"
            title="删除"
          >
            <Trash2 className="w-4 h-4" />
          </button>
          <Link
            to={`/traces/${t.trace_id}`}
            className="p-1.5 text-slate-400 hover:text-indigo-600 rounded hover:bg-indigo-50 transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </Link>
        </div>
      </td>
    </tr>
  );
}

function ThreadCard({ group }: { group: ThreadGroup }) {
  const statuses = [...new Set(group.traces.map((t) => t.status))];
  const hasFailed = statuses.includes("failed");

  return (
    <Link
      to={`/threads/${encodeURIComponent(group.thread_id)}`}
      className="card block hover:shadow-md transition-shadow group"
    >
      {/* 会话头：合并显示，整张卡可点击进入会话详情 */}
      <div className="flex items-center gap-3 px-4 py-3.5 bg-gradient-to-r from-indigo-50/80 to-slate-50/80 group-hover:from-indigo-100/80 group-hover:to-slate-100/80 transition-colors">
        <MessagesSquare className="w-5 h-5 text-indigo-500 shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-800 mono">
              {group.thread_id}
            </span>
            <span className="text-xs text-slate-500 bg-white px-2 py-0.5 rounded-full border border-slate-200">
              {group.traces.length} 次调用
            </span>
            {hasFailed && <Badge variant="failed">含失败</Badge>}
          </div>
          <div className="text-xs text-slate-500 mt-0.5 flex items-center gap-2">
            <span className="mono">{fmtRange(group.start_time, group.end_time)}</span>
            <span className="text-slate-300">·</span>
            <span>最近：{group.latest.name ?? group.latest.trace_id.slice(0, 8)}</span>
          </div>
        </div>
        <ChevronRight className="w-4 h-4 text-slate-400 group-hover:text-indigo-600 group-hover:translate-x-0.5 transition-all shrink-0" />
      </div>
    </Link>
  );
}

interface Props {
  traces: Trace[];
  loading?: boolean;
}

export default function TraceListTable({ traces, loading }: Props) {
  const [view, setView] = useState<"session" | "trace">("session");

  if (!loading && traces.length === 0) {
    return (
      <div className="card flex flex-col items-center justify-center py-16 text-center">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3">
          <Inbox className="w-6 h-6 text-slate-400" />
        </div>
        <p className="text-sm font-medium text-slate-600">暂无 Trace 记录</p>
        <p className="text-xs text-slate-400 mt-1">
          通过 AI Agent callback 推送，或在
          <a href="http://localhost:8000/docs" target="_blank" rel="noreferrer" className="text-indigo-600 mx-1 hover:underline">
            API 文档
          </a>
          手动 POST 一条
        </p>
      </div>
    );
  }

  // 视图切换
  const toolbar = (
    <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-0.5 shadow-sm">
      <button
        onClick={() => setView("session")}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
          view === "session"
            ? "bg-indigo-600 text-white"
            : "text-slate-600 hover:bg-slate-100"
        }`}
      >
        <Layers className="w-3.5 h-3.5" />
        会话视图
      </button>
      <button
        onClick={() => setView("trace")}
        className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
          view === "trace"
            ? "bg-indigo-600 text-white"
            : "text-slate-600 hover:bg-slate-100"
        }`}
      >
        <List className="w-3.5 h-3.5" />
        Trace 视图
      </button>
    </div>
  );

  if (view === "trace") {
    return (
      <div className="space-y-4">
        <div className="flex justify-end">{toolbar}</div>
        <div className="card overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                <th className="text-left font-medium px-4 py-2.5">名称</th>
                <th className="text-left font-medium px-4 py-2.5">会话</th>
                <th className="text-left font-medium px-4 py-2.5">状态</th>
                <th className="text-left font-medium px-4 py-2.5">事件</th>
                <th className="text-left font-medium px-4 py-2.5">耗时</th>
                <th className="text-left font-medium px-4 py-2.5">开始时间</th>
                <th className="text-right font-medium px-4 py-2.5 w-20">操作</th>
              </tr>
            </thead>
            <tbody>
              {traces.map((t) => (
                <TraceRow key={t.trace_id} t={t} showThread />
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  }

  // 会话视图（默认）：同 thread_id 合并
  const { threads, standalone } = groupByThread(traces);
  return (
    <div className="space-y-4">
      <div className="flex justify-end">{toolbar}</div>

      {threads.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide px-1">
            会话（{threads.length}）
          </div>
          {threads.map((g) => (
            <ThreadCard key={g.thread_id} group={g} />
          ))}
        </div>
      )}

      {standalone.length > 0 && (
        <div className="space-y-3">
          <div className="text-xs font-semibold text-slate-500 uppercase tracking-wide px-1">
            独立 Trace（{standalone.length}）
          </div>
          <div className="card overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="bg-slate-50 text-slate-500 text-xs uppercase tracking-wide">
                  <th className="text-left font-medium px-4 py-2.5">名称</th>
                  <th className="text-left font-medium px-4 py-2.5">状态</th>
                  <th className="text-left font-medium px-4 py-2.5">事件</th>
                  <th className="text-left font-medium px-4 py-2.5">耗时</th>
                  <th className="text-left font-medium px-4 py-2.5">开始时间</th>
                  <th className="text-right font-medium px-4 py-2.5 w-20">操作</th>
                </tr>
              </thead>
              <tbody>
                {standalone.map((t) => (
                  <TraceRow key={t.trace_id} t={t} />
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
