import { BarChart3 } from "lucide-react";
import StatsPanel from "@/components/StatsPanel";

export default function StatsPage() {
  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* 顶栏 */}
      <header className="h-16 shrink-0 bg-white/80 backdrop-blur border-b border-slate-200 px-8 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-indigo-50 flex items-center justify-center">
            <BarChart3 className="w-4.5 h-4.5 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-slate-900 leading-none">Token 统计</h1>
            <p className="text-xs text-slate-500 mt-0.5">Token 消耗概览与多维分析</p>
          </div>
        </div>
      </header>

      {/* 内容 */}
      <div className="flex-1 overflow-auto px-8 py-6">
        <StatsPanel />
      </div>
    </div>
  );
}
