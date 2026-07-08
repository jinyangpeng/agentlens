import { useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, PieChart, Pie, Cell,
} from "recharts";
import {
  Activity, Database, Hash, Percent, Timer, Layers, User, AppWindow,
  Calendar, Inbox,
} from "lucide-react";
import { Skeleton } from "@/components/ui/Skeleton";
import { useOverview, useTokenStats } from "@/hooks/useStats";
import type { StatsDimension } from "@/types/stats";

const DIMENSIONS: { key: StatsDimension; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "session", label: "会话", icon: Layers },
  { key: "user", label: "用户", icon: User },
  { key: "app", label: "应用", icon: AppWindow },
];

const PROMPT_COLOR = "#4f46e5";     // indigo-600
const COMPLETION_COLOR = "#10b981"; // emerald-500
const PIE_COLORS = [
  "#4f46e5", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
  "#06b6d4", "#ec4899", "#84cc16", "#f97316", "#6366f1",
];

function formatNumber(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return String(n);
}

function formatPercent(n: number): string {
  return `${(n * 100).toFixed(1)}%`;
}

interface OverviewCardProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
  hint?: string;
  accent: string;
}

function OverviewCard({ icon: Icon, label, value, hint, accent }: OverviewCardProps) {
  return (
    <div className="card p-4 flex items-start gap-3">
      <div
        className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
        style={{ backgroundColor: `${accent}1a`, color: accent }}
      >
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <div className="text-xs text-slate-500">{label}</div>
        <div className="text-xl font-semibold text-slate-900 mt-0.5 mono">{value}</div>
        {hint && <div className="text-[11px] text-slate-400 mt-0.5">{hint}</div>}
      </div>
    </div>
  );
}

function OverviewSkeleton() {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
      {Array.from({ length: 5 }).map((_, i) => (
        <div key={i} className="card p-4">
          <Skeleton className="h-10 w-10 rounded-lg" />
          <Skeleton className="h-3 w-16 mt-3" />
          <Skeleton className="h-5 w-20 mt-2" />
        </div>
      ))}
    </div>
  );
}

interface BarTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string }>;
  label?: string;
}

function BarTooltip({ active, payload, label }: BarTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const total = payload.reduce((s, p) => s + (p.value ?? 0), 0);
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <div className="font-medium text-slate-800 mb-1.5 truncate max-w-[220px]">{label}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center gap-2 text-slate-600">
          <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: p.color }} />
          <span>{p.name}</span>
          <span className="ml-auto mono font-medium">{formatNumber(p.value)}</span>
        </div>
      ))}
      <div className="flex items-center gap-2 text-slate-500 mt-1 pt-1 border-t border-slate-100">
        <span>合计</span>
        <span className="ml-auto mono font-medium">{formatNumber(total)}</span>
      </div>
    </div>
  );
}

interface PieTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; payload: { percent: number } }>;
}

function PieTooltip({ active, payload }: PieTooltipProps) {
  if (!active || !payload || payload.length === 0) return null;
  const p = payload[0];
  return (
    <div className="bg-white border border-slate-200 rounded-lg shadow-lg px-3 py-2 text-xs">
      <div className="font-medium text-slate-800 mb-0.5 truncate max-w-[200px]">{p.name}</div>
      <div className="text-slate-600 mono">{formatNumber(p.value)} ({formatPercent(p.payload.percent)})</div>
    </div>
  );
}

function ChartSkeleton() {
  return (
    <div className="card p-4">
      <Skeleton className="h-5 w-32 mb-4" />
      <Skeleton className="h-64 w-full" />
    </div>
  );
}

function EmptyChart({ message }: { message: string }) {
  return (
    <div className="card p-4">
      <div className="flex flex-col items-center justify-center py-16 text-center">
        <div className="w-12 h-12 rounded-full bg-slate-100 flex items-center justify-center mb-3">
          <Inbox className="w-6 h-6 text-slate-400" />
        </div>
        <p className="text-sm font-medium text-slate-600">{message}</p>
      </div>
    </div>
  );
}

export default function StatsPanel() {
  const [dimension, setDimension] = useState<StatsDimension>("session");
  const [startDate, setStartDate] = useState("");
  const [endDate, setEndDate] = useState("");

  const overview = useOverview();
  const tokenStats = useTokenStats(
    dimension,
    startDate || undefined,
    endDate || undefined
  );

  const pieData = useMemo(() => {
    if (!tokenStats.data) return [];
    return tokenStats.data.items
      .map((it) => ({ name: it.label, value: it.total_tokens }))
      .filter((d) => d.value > 0);
  }, [tokenStats.data]);

  const overviewCards = useMemo(() => {
    const o = overview.data;
    if (!o) return null;
    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
        <OverviewCard
          icon={Activity}
          label="Trace 总数"
          value={formatNumber(o.total_traces)}
          accent="#4f46e5"
        />
        <OverviewCard
          icon={Database}
          label="Token 总量"
          value={formatNumber(o.total_tokens)}
          accent="#10b981"
        />
        <OverviewCard
          icon={Layers}
          label="会话总数"
          value={formatNumber(o.total_sessions)}
          accent="#f59e0b"
        />
        <OverviewCard
          icon={Timer}
          label="平均 Token / Trace"
          value={formatNumber(Math.round(o.avg_tokens_per_trace))}
          accent="#8b5cf6"
        />
        <OverviewCard
          icon={Percent}
          label="成功率"
          value={formatPercent(o.success_rate)}
          accent="#06b6d4"
        />
      </div>
    );
  }, [overview.data]);

  return (
    <div className="space-y-5">
      {/* 概览卡片 */}
      {overview.isLoading ? (
        <OverviewSkeleton />
      ) : overview.isError || !overviewCards ? (
        <div className="card p-8 text-center">
          <p className="text-sm text-red-600">概览数据加载失败</p>
        </div>
      ) : (
        overviewCards
      )}

      {/* 控制栏：维度切换 + 日期筛选 */}
      <div className="card p-3 flex flex-wrap items-center gap-3 justify-between">
        <div className="flex items-center gap-1 bg-slate-50 border border-slate-200 rounded-lg p-0.5">
          {DIMENSIONS.map((d) => {
            const Icon = d.icon;
            const active = dimension === d.key;
            return (
              <button
                key={d.key}
                onClick={() => setDimension(d.key)}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-md transition-colors ${
                  active
                    ? "bg-indigo-600 text-white shadow-sm"
                    : "text-slate-600 hover:bg-slate-100"
                }`}
              >
                <Icon className="w-3.5 h-3.5" />
                {d.label}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <Calendar className="w-3.5 h-3.5 text-slate-400" />
          <input
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            className="border border-slate-200 rounded-md px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
          <span className="text-slate-400">至</span>
          <input
            type="date"
            value={endDate}
            onChange={(e) => setEndDate(e.target.value)}
            className="border border-slate-200 rounded-md px-2 py-1 text-xs text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-500/30"
          />
          {(startDate || endDate) && (
            <button
              onClick={() => {
                setStartDate("");
                setEndDate("");
              }}
              className="text-slate-400 hover:text-red-600 transition-colors px-1"
              title="清除日期筛选"
            >
              清除
            </button>
          )}
        </div>
      </div>

      {/* 图表区：柱状图 + 饼图 */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* 柱状图 */}
        <div className="xl:col-span-2">
          {tokenStats.isLoading ? (
            <ChartSkeleton />
          ) : tokenStats.isError ? (
            <div className="card p-8 text-center">
              <p className="text-sm text-red-600">Token 统计加载失败</p>
            </div>
          ) : !tokenStats.data || tokenStats.data.items.length === 0 ? (
            <EmptyChart message="当前维度下暂无 Token 数据" />
          ) : (
            <div className="card p-4">
              <div className="flex items-center justify-between mb-3">
                <div>
                  <h3 className="text-sm font-semibold text-slate-800">Token 消耗分布</h3>
                  <p className="text-xs text-slate-500 mt-0.5">
                    按{DIMENSIONS.find((d) => d.key === dimension)?.label}维度 · 堆叠柱状图
                  </p>
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: PROMPT_COLOR }} />
                    Prompt
                  </span>
                  <span className="inline-flex items-center gap-1">
                    <span className="w-2.5 h-2.5 rounded-sm" style={{ backgroundColor: COMPLETION_COLOR }} />
                    Completion
                  </span>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={320}>
                <BarChart
                  data={tokenStats.data.items}
                  margin={{ top: 8, right: 16, left: 8, bottom: 8 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
                  <XAxis
                    dataKey="label"
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickLine={false}
                    axisLine={{ stroke: "#e2e8f0" }}
                    interval={0}
                    angle={-15}
                    textAnchor="end"
                    height={60}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "#64748b" }}
                    tickLine={false}
                    axisLine={false}
                    tickFormatter={formatNumber}
                  />
                  <Tooltip content={<BarTooltip />} cursor={{ fill: "#f1f5f9" }} />
                  <Legend wrapperStyle={{ display: "none" }} />
                  <Bar
                    dataKey="prompt_tokens"
                    name="Prompt"
                    stackId="tokens"
                    fill={PROMPT_COLOR}
                    maxBarSize={48}
                  />
                  <Bar
                    dataKey="completion_tokens"
                    name="Completion"
                    stackId="tokens"
                    fill={COMPLETION_COLOR}
                    maxBarSize={48}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>

        {/* 饼图 */}
        <div>
          {tokenStats.isLoading ? (
            <ChartSkeleton />
          ) : tokenStats.isError ? (
            <div className="card p-8 text-center">
              <p className="text-sm text-red-600">Token 统计加载失败</p>
            </div>
          ) : pieData.length === 0 ? (
            <EmptyChart message="暂无可占比数据" />
          ) : (
            <div className="card p-4">
              <div className="mb-3">
                <h3 className="text-sm font-semibold text-slate-800">Token 占比</h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  总计 {formatNumber(tokenStats.data?.totals.total_tokens ?? 0)} tokens
                </p>
              </div>
              <ResponsiveContainer width="100%" height={240}>
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    cx="50%"
                    cy="50%"
                    innerRadius={50}
                    outerRadius={85}
                    paddingAngle={2}
                  >
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip content={<PieTooltip />} />
                </PieChart>
              </ResponsiveContainer>
              <div className="mt-2 space-y-1 max-h-[120px] overflow-y-auto">
                {pieData.slice(0, 8).map((d, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs">
                    <span
                      className="w-2.5 h-2.5 rounded-sm shrink-0"
                      style={{ backgroundColor: PIE_COLORS[i % PIE_COLORS.length] }}
                    />
                    <span className="text-slate-600 truncate flex-1">{d.name}</span>
                    <span className="text-slate-500 mono">{formatNumber(d.value)}</span>
                  </div>
                ))}
                {pieData.length > 8 && (
                  <div className="text-[11px] text-slate-400 pl-4.5">
                    还有 {pieData.length - 8} 项…
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* 汇总条 */}
      {tokenStats.data && (
        <div className="card p-3 flex flex-wrap items-center gap-x-6 gap-y-2 text-xs">
          <div className="inline-flex items-center gap-1.5 text-slate-500">
            <Hash className="w-3.5 h-3.5" />
            <span>调用次数</span>
            <span className="mono font-semibold text-slate-800">
              {formatNumber(tokenStats.data.totals.call_count)}
            </span>
          </div>
          <div className="inline-flex items-center gap-1.5 text-slate-500">
            <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: PROMPT_COLOR }} />
            <span>Prompt</span>
            <span className="mono font-semibold text-slate-800">
              {formatNumber(tokenStats.data.totals.prompt_tokens)}
            </span>
          </div>
          <div className="inline-flex items-center gap-1.5 text-slate-500">
            <span className="w-2 h-2 rounded-sm" style={{ backgroundColor: COMPLETION_COLOR }} />
            <span>Completion</span>
            <span className="mono font-semibold text-slate-800">
              {formatNumber(tokenStats.data.totals.completion_tokens)}
            </span>
          </div>
          <div className="inline-flex items-center gap-1.5 text-slate-500">
            <Database className="w-3.5 h-3.5" />
            <span>合计</span>
            <span className="mono font-semibold text-slate-800">
              {formatNumber(tokenStats.data.totals.total_tokens)}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
