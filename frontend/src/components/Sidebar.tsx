import { Link, useLocation } from "react-router-dom";
import { Activity, ListTree, Github, BookOpen } from "lucide-react";

const NAV = [
  { to: "/", label: "Traces", icon: ListTree, desc: "调用轨迹" },
];

export default function Sidebar() {
  const { pathname } = useLocation();
  return (
    <aside className="w-60 shrink-0 flex flex-col bg-[rgb(var(--sidebar))] text-slate-300">
      {/* 品牌 */}
      <div className="h-16 flex items-center gap-2.5 px-5 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg bg-indigo-600 flex items-center justify-center shadow-lg shadow-indigo-900/40">
          <Activity className="w-4.5 h-4.5 text-white" strokeWidth={2.5} />
        </div>
        <div className="leading-tight">
          <div className="text-sm font-semibold text-white">AgentLens</div>
          <div className="text-[11px] text-slate-500">Agent Observability</div>
        </div>
      </div>

      {/* 导航 */}
      <nav className="flex-1 px-3 py-4 space-y-1">
        <div className="px-2 pb-2 text-[11px] font-medium uppercase tracking-wider text-slate-600">
          导航
        </div>
        {NAV.map((item) => {
          const active = item.to === "/" ? pathname === "/" : pathname.startsWith(item.to);
          const Icon = item.icon;
          return (
            <Link
              key={item.to}
              to={item.to}
              className={`flex items-center gap-3 px-2.5 py-2 rounded-md text-sm transition-colors ${
                active
                  ? "bg-white/10 text-white"
                  : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="flex-1">{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* 底部 */}
      <div className="p-3 border-t border-white/5 space-y-1">
        <a
          href="/docs"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 px-2.5 py-2 rounded-md text-sm text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors"
        >
          <BookOpen className="w-4 h-4" />
          <span>API 文档</span>
        </a>
        <a
          href="https://github.com"
          target="_blank"
          rel="noreferrer"
          className="flex items-center gap-3 px-2.5 py-2 rounded-md text-sm text-slate-400 hover:bg-white/5 hover:text-slate-200 transition-colors"
        >
          <Github className="w-4 h-4" />
          <span>仓库</span>
        </a>
        <div className="px-2.5 pt-2 mt-2 border-t border-white/5 flex items-center gap-2">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
          <span className="text-[11px] text-slate-500">后端已连接</span>
        </div>
      </div>
    </aside>
  );
}
