import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft, MessageSquare, Network, Clock, MessagesSquare,
} from "lucide-react";
import MessageFlow from "@/components/MessageFlow";
import EventTimeline from "@/components/EventTimeline";
import CallTree from "@/components/CallTree";
import { Skeleton } from "@/components/ui/Skeleton";
import { Badge } from "@/components/ui/Badge";
import { useThreadTraces } from "@/hooks/useTraces";
import type { Trace, TraceEvent } from "@/types/trace";

type Tab = "messages" | "tree" | "timeline";

const TABS: { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "messages", label: "消息流", icon: MessageSquare },
  { key: "tree", label: "调用树", icon: Network },
  { key: "timeline", label: "时间线", icon: Clock },
];

/** 合并会话所有 trace 的事件，按时间排序；同时注入 _source 字段标注来源 trace */
function mergeEvents(
  traces: Trace[]
): (TraceEvent & { _source?: { index: number; name: string; trace_id: string } })[] {
  const arr: (TraceEvent & { _source?: { index: number; name: string; trace_id: string } })[] = [];
  traces.forEach((t, i) => {
    const name = t.name ?? t.trace_id.slice(0, 8);
    t.events.forEach((e) => {
      arr.push({ ...e, _source: { index: i, name, trace_id: t.trace_id } });
    });
  });
  arr.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
  return arr;
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

export default function ThreadDetailPage() {
  const { threadId } = useParams<{ threadId: string }>();
  const { data: traces, isLoading, isError } = useThreadTraces(threadId!);
  const [tab, setTab] = useState<Tab>("messages");

  const sorted = (traces ?? []).slice().sort(
    (a, b) =>
      new Date(a.start_time ?? 0).getTime() - new Date(b.start_time ?? 0).getTime()
  );
  const totalEvents = sorted.reduce((n, t) => n + t.events.length, 0);
  const hasFailed = sorted.some((t) => t.status === "failed");
  const startTimes = sorted.map((t) => t.start_time).filter((x): x is string => !!x);
  const start = startTimes[0] ?? null;
  const end = startTimes[startTimes.length - 1] ?? null;
  const mergedEvents = mergeEvents(sorted);

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* 顶栏 */}
      <header className="h-12 shrink-0 bg-white border-b border-slate-200 px-6 flex items-center gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>返回</span>
        </Link>
        <span className="text-slate-300">/</span>
        <span className="text-sm text-slate-500">会话详情</span>
      </header>

      {isLoading ? (
        <div className="space-y-3 p-6">
          <Skeleton className="h-8 w-full" />
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-16 w-full" />
        </div>
      ) : isError || sorted.length === 0 ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-sm text-red-600">未找到该会话的 Trace</p>
            <Link to="/" className="text-xs text-indigo-600 hover:underline mt-2 inline-block">
              返回列表
            </Link>
          </div>
        </div>
      ) : (
        <>
          {/* 会话基本信息 + Tabs（固定不滚动） */}
          <div className="shrink-0 bg-white border-b border-slate-200 px-6 pt-3 pb-0">
            <div className="flex items-center gap-2 flex-wrap text-sm">
              <MessagesSquare className="w-4 h-4 text-indigo-500" />
              <h1 className="font-semibold text-slate-900 mono">{threadId}</h1>
              <span className="text-xs text-slate-500 bg-slate-100 px-2 py-0.5 rounded-full">
                {sorted.length} 次调用
              </span>
              <span className="text-xs text-slate-500 mono">{totalEvents} 事件</span>
              {hasFailed && <Badge variant="failed">含失败</Badge>}
              <span className="text-xs text-slate-500 mono ml-auto">
                {fmtRange(start, end)}
              </span>
            </div>
            <nav className="flex gap-1 mt-2.5">
              {TABS.map((t) => {
                const Icon = t.icon;
                const active = tab === t.key;
                return (
                  <button
                    key={t.key}
                    onClick={() => setTab(t.key)}
                    className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-medium border-b-2 -mb-px transition-colors ${
                      active
                        ? "border-indigo-600 text-indigo-600"
                        : "border-transparent text-slate-500 hover:text-slate-800"
                    }`}
                  >
                    <Icon className="w-4 h-4" />
                    {t.label}
                  </button>
                );
              })}
            </nav>
          </div>

          {/* 内容区：仅此滚动 */}
          <div className="flex-1 overflow-y-auto bg-slate-50">
            <div className="max-w-5xl mx-auto px-6 py-5">
              {tab === "messages" && (
                <div className="space-y-6">
                  {sorted.map((t, idx) => (
                    <div key={t.trace_id}>
                      {/* trace 分界条 */}
                      <div className="flex items-center gap-2 mb-3 sticky top-0 bg-slate-50/95 backdrop-blur-sm py-1.5 z-10">
                        <span className="text-xs font-semibold text-indigo-600 mono px-2 py-0.5 rounded-full bg-indigo-50 border border-indigo-200">
                          调用 #{idx + 1}
                        </span>
                        <Link
                          to={`/traces/${t.trace_id}`}
                          className="text-xs text-slate-600 hover:text-indigo-600 font-medium truncate"
                        >
                          {t.name ?? t.trace_id.slice(0, 8)}
                        </Link>
                        <Badge
                          variant={
                            t.status === "succeeded" ? "success" : t.status === "failed" ? "failed" : "running"
                          }
                        >
                          {t.status}
                        </Badge>
                        {t.duration_ms != null && (
                          <span className="text-xs text-slate-500 mono">{t.duration_ms}ms</span>
                        )}
                        {t.start_time && (
                          <span className="text-xs text-slate-400 mono">
                            {new Date(t.start_time).toLocaleString("zh-CN", { hour12: false })}
                          </span>
                        )}
                      </div>
                      <MessageFlow
                        messages={t.messages}
                        structuredResponse={t.structured_response}
                        events={t.events}
                        startTime={t.start_time}
                      />
                    </div>
                  ))}
                </div>
              )}
              {tab === "tree" && <CallTree events={mergedEvents} />}
              {tab === "timeline" && (
                <EventTimeline
                  events={mergedEvents}
                  getSourceIndex={(e) =>
                    (e as TraceEvent & { _source?: { index: number; name: string; trace_id: string } })._source?.index
                  }
                  getSourceName={(e) =>
                    (e as TraceEvent & { _source?: { index: number; name: string; trace_id: string } })._source?.name
                  }
                />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
