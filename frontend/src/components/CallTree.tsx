import { useState } from "react";
import { ChevronRight, ChevronDown, Settings2 } from "lucide-react";
import type { TraceEvent } from "@/types/trace";
import { Badge } from "./ui/Badge";
import JsonViewer from "./JsonViewer";
import {
  KIND_META, buildRunTree, fmtDuration, isEmpty, shortId,
  type RunNode,
} from "@/lib/callTree";

interface Props {
  events: TraceEvent[];
}

function fmtTime(ts: string | null): string {
  if (!ts) return "";
  return new Date(ts).toLocaleTimeString("zh-CN", { hour12: false });
}

function RunNodeCard({ node, depth }: { node: RunNode; depth: number }) {
  const [open, setOpen] = useState(depth < 1);
  const [showIO, setShowIO] = useState(false);
  const meta = KIND_META[node.kind];
  const Icon = meta.icon;
  const hasIO = !isEmpty(node.inputs) || !isEmpty(node.outputs);
  const hasChildren = node.children.length > 0;

  return (
    <div className="relative" style={{ paddingLeft: depth > 0 ? 24 : 0 }}>
      {depth > 0 && (
        <span className="absolute left-0 top-0 bottom-0 w-px bg-slate-200" aria-hidden />
      )}
      {depth > 0 && (
        <span className="absolute left-0 top-4 w-5 h-px bg-slate-200" aria-hidden />
      )}

      <div
        className={`rounded-lg border bg-white transition-all hover:shadow-sm ${
          node.is_middleware
            ? "border-orange-300 ring-1 ring-orange-200"
            : node.status === "failed"
              ? "border-red-200"
              : "border-slate-200"
        }`}
      >
        <div
          className={`flex items-center gap-2 px-3 py-2 cursor-pointer select-none ${
            hasIO ? "hover:bg-slate-50" : ""
          }`}
          onClick={() => hasIO && setShowIO((v) => !v)}
        >
          {hasChildren ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                setOpen((v) => !v);
              }}
              className="p-0.5 text-slate-400 hover:text-slate-700 rounded hover:bg-slate-100 transition-colors"
            >
              {open ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
            </button>
          ) : (
            <span className="w-[18px] shrink-0" />
          )}

          <span className={`inline-flex items-center justify-center w-5 h-5 rounded ${meta.bg} shrink-0`}>
            <Icon className={`w-3.5 h-3.5 ${meta.color}`} />
          </span>

          <span className="text-sm font-medium text-slate-800 truncate">
            {node.className || meta.label}
          </span>
          {node.name && node.name !== node.className && (
            <span className="text-xs text-slate-400 truncate">({node.name})</span>
          )}
          <span className={`text-[10px] mono px-1.5 py-0.5 rounded ${meta.bg} ${meta.color} shrink-0`}>
            {meta.label}
          </span>
          {node.is_middleware && (
            <span className="inline-flex items-center gap-1 text-[10px] mono px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200 shrink-0">
              <Settings2 className="w-3 h-3" />
              {node.middleware_name || "Middleware"}
            </span>
          )}

          {node.status === "failed" && <Badge variant="failed">失败</Badge>}
          {node.status === "running" && <Badge variant="running">运行中</Badge>}

          <span className="ml-auto flex items-center gap-2 text-[11px] text-slate-400 shrink-0">
            {node.duration_ms != null && (
              <span className="mono font-medium text-slate-600">{fmtDuration(node.duration_ms)}</span>
            )}
            {node.start_time && <span className="mono">{fmtTime(node.start_time)}</span>}
            <span className="mono text-slate-300" title={node.run_id}>#{shortId(node.run_id)}</span>
          </span>
        </div>

        {(node.inputSummary || node.outputSummary) && (
          <div className="px-3 pb-2 pt-0.5 space-y-0.5 text-xs">
            {node.inputSummary && (
              <div className="flex gap-1.5 text-slate-500">
                <span className="text-slate-400 font-medium shrink-0">输入</span>
                <span className="text-slate-600 truncate">{node.inputSummary}</span>
              </div>
            )}
            {node.outputSummary && (
              <div className="flex gap-1.5 text-slate-500">
                <span className="text-slate-400 font-medium shrink-0">输出</span>
                <span className="text-slate-600 truncate">{node.outputSummary}</span>
              </div>
            )}
          </div>
        )}

        {node.error && (
          <div className="mx-3 mb-2 text-xs text-red-700 bg-red-50 border border-red-200 rounded px-2 py-1">
            <span className="font-mono font-medium">{node.error.type}:</span> {node.error.message}
          </div>
        )}

        {showIO && hasIO && (
          <div className="mx-3 mb-2 pt-1 border-t border-slate-100 space-y-1.5">
            {!isEmpty(node.inputs) && <JsonViewer data={node.inputs} label="输入" defaultOpen />}
            {!isEmpty(node.outputs) && <JsonViewer data={node.outputs} label="输出" defaultOpen />}
          </div>
        )}
      </div>

      {open && hasChildren && (
        <div className="mt-1.5 space-y-1.5">
          {node.children.map((c) => (
            <RunNodeCard key={c.run_id} node={c} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export default function CallTree({ events }: Props) {
  const roots = buildRunTree(events);
  if (roots.length === 0) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p className="text-sm">无事件</p>
      </div>
    );
  }
  return (
    <div className="space-y-1.5">
      {roots.map((r) => (
        <RunNodeCard key={r.run_id} node={r} depth={0} />
      ))}
    </div>
  );
}
