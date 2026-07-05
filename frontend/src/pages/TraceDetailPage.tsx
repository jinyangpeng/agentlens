import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Network, Clock, MessageSquare, Code2 } from "lucide-react";
import TraceDetailHeader from "@/components/TraceDetailHeader";
import EventTimeline from "@/components/EventTimeline";
import CallTree from "@/components/CallTree";
import MessageFlow from "@/components/MessageFlow";
import JsonViewer from "@/components/JsonViewer";
import { Skeleton } from "@/components/ui/Skeleton";
import { useTrace } from "@/hooks/useTraces";

type Tab = "tree" | "timeline" | "messages" | "io";

const TABS: { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "messages", label: "消息流", icon: MessageSquare },
  { key: "tree", label: "调用树", icon: Network },
  { key: "timeline", label: "时间线", icon: Clock },
  { key: "io", label: "输入/输出", icon: Code2 },
];

function DetailSkeleton() {
  return (
    <div className="space-y-3 p-6">
      <Skeleton className="h-8 w-full" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
    </div>
  );
}

export default function TraceDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const { data: trace, isLoading, isError } = useTrace(traceId!);
  const [tab, setTab] = useState<Tab>("messages");

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* 顶栏：返回 + 面包屑（固定不滚动） */}
      <header className="h-12 shrink-0 bg-white border-b border-slate-200 px-6 flex items-center gap-3">
        <Link
          to="/"
          className="inline-flex items-center gap-1.5 text-sm text-slate-600 hover:text-indigo-600 transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>返回</span>
        </Link>
        <span className="text-slate-300">/</span>
        <span className="text-sm text-slate-500">Trace 详情</span>
      </header>

      {/* 基本信息 + Tabs（固定不滚动，紧凑布局） */}
      {isLoading ? (
        <DetailSkeleton />
      ) : isError || !trace ? (
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center">
            <p className="text-sm text-red-600">未找到该 Trace</p>
            <Link to="/" className="text-xs text-indigo-600 hover:underline mt-2 inline-block">
              返回列表
            </Link>
          </div>
        </div>
      ) : (
        <>
          <div className="shrink-0 bg-white border-b border-slate-200 px-6 pt-3 pb-0">
            <TraceDetailHeader trace={trace} />
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

          {/* 内容区：仅此区域滚动 */}
          <div className="flex-1 overflow-y-auto bg-slate-50">
            <div className="max-w-5xl mx-auto px-6 py-5">
              {tab === "tree" && <CallTree events={trace.events} />}
              {tab === "timeline" && <EventTimeline events={trace.events} />}
              {tab === "messages" && (
                <MessageFlow
                  messages={trace.messages}
                  structuredResponse={trace.structured_response}
                  events={trace.events}
                  startTime={trace.start_time}
                />
              )}
              {tab === "io" && (
                <div className="space-y-3">
                  <JsonViewer data={trace.input} label="输入 (input)" defaultOpen />
                  <JsonViewer data={trace.output} label="输出 (output)" defaultOpen />
                  <JsonViewer data={trace.metadata} label="元数据 (metadata)" />
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
