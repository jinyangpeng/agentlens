import { useState } from "react";
import { useSearchParams, Link } from "react-router-dom";
import { ChevronLeft, ChevronRight, ListTree, MessagesSquare, X } from "lucide-react";
import TraceListTable from "@/components/TraceListTable";
import { Skeleton } from "@/components/ui/Skeleton";
import { useTraces } from "@/hooks/useTraces";

function ListSkeleton() {
  return (
    <div className="card overflow-hidden">
      <div className="p-3 space-y-2">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-4 flex-1" />
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-12" />
            <Skeleton className="h-4 w-20" />
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TraceListPage() {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const [searchParams, setSearchParams] = useSearchParams();
  const threadId = searchParams.get("thread_id") ?? undefined;
  const { data, isLoading, isError } = useTraces(limit, offset, threadId);

  const total = data?.length ?? 0;
  const hasNext = total === limit;
  const hasPrev = offset > 0;

  const clearThreadFilter = () => {
    searchParams.delete("thread_id");
    setSearchParams(searchParams, { replace: true });
    setOffset(0);
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* 顶栏 */}
      <header className="h-16 shrink-0 bg-white/80 backdrop-blur border-b border-slate-200 px-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
            <ListTree className="w-4.5 h-4.5 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-900 leading-none">Trace 日志</h1>
            <p className="text-xs text-slate-500 mt-0.5">LangChain 调用轨迹列表</p>
          </div>
        </div>
        <div className="flex items-center gap-1 text-sm text-slate-500">
          <button
            onClick={() => setOffset(Math.max(0, offset - limit))}
            disabled={!hasPrev}
            className="p-1.5 rounded-md border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronLeft className="w-4 h-4" />
          </button>
          <span className="px-2 mono text-xs">
            {offset + 1}–{offset + total}
          </span>
          <button
            onClick={() => setOffset(offset + limit)}
            disabled={!hasNext}
            className="p-1.5 rounded-md border border-slate-200 hover:bg-slate-50 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <ChevronRight className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* 会话筛选条 */}
      {threadId && (
        <div className="shrink-0 bg-indigo-50/60 border-b border-indigo-100 px-8 py-2 flex items-center gap-2">
          <MessagesSquare className="w-3.5 h-3.5 text-indigo-500" />
          <span className="text-xs text-slate-600">会话筛选：</span>
          <span className="text-xs mono font-medium text-indigo-700 px-1.5 py-0.5 rounded bg-white border border-indigo-200">
            {threadId}
          </span>
          <button
            onClick={clearThreadFilter}
            className="inline-flex items-center gap-0.5 text-xs text-slate-500 hover:text-red-600 ml-1"
          >
            <X className="w-3 h-3" />
            清除
          </button>
        </div>
      )}

      {/* 内容 */}
      <div className="flex-1 overflow-auto px-8 py-6">
        {isLoading ? (
          <ListSkeleton />
        ) : isError ? (
          <div className="card p-12 text-center">
            <p className="text-sm text-red-600">加载失败，请确认后端服务已启动</p>
            <p className="text-xs text-slate-400 mt-1">运行 `python -m uvicorn app.main:app --reload`</p>
          </div>
        ) : (
          <TraceListTable traces={data ?? []} loading={isLoading} />
        )}
      </div>
    </div>
  );
}
