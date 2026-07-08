import { Fragment } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import {
  Wrench, Clock, Settings2,
  FileText, UserCheck, Gauge, Repeat, ShieldAlert,
  ListTodo, MousePointerClick, RefreshCw, Terminal,
  Edit3, SquareTerminal, FolderSearch,
  type LucideIcon,
} from "lucide-react";
import type { TraceEvent } from "@/types/trace";

interface ResponseMeta {
  model_name?: string;
  model?: string;
  model_provider?: string;
}

interface Message {
  id?: string;
  content?: unknown;
  type?: string;
  _type?: string;
  name?: string;
  tool_call_id?: string;
  tool_calls?: Array<{ name?: string; args?: unknown; id?: string; type?: string }>;
  response_metadata?: ResponseMeta;
  additional_kwargs?: Record<string, unknown>;
}

interface Props {
  messages: unknown[];
  structuredResponse?: unknown;
  events?: TraceEvent[];
  startTime?: string | null;
}

// ---- Middleware 配置表（与后端 middleware_registry.py 对齐） ----

interface MiddlewareConf {
  className: string; // 标准类名（用于显示和旧数据回填匹配）
  label: string; // 显示名
  icon: LucideIcon; // 图标组件
  color: string; // 文字颜色 e.g. "text-purple-600"
  bg: string; // 背景色 e.g. "bg-purple-50"
  border: string; // 边框色 e.g. "border-purple-200"
  dot: string; // 圆点色 e.g. "bg-purple-500"
  description: string; // 简短描述
}

const MIDDLEWARE_CONF: Record<string, MiddlewareConf> = {
  summarization: {
    className: "SummarizationMiddleware",
    label: "摘要压缩",
    icon: FileText,
    color: "text-purple-600",
    bg: "bg-purple-50",
    border: "border-purple-200",
    dot: "bg-purple-500",
    description: "自动摘要历史消息",
  },
  human_in_the_loop: {
    className: "HumanInTheLoopMiddleware",
    label: "人工审批",
    icon: UserCheck,
    color: "text-amber-600",
    bg: "bg-amber-50",
    border: "border-amber-200",
    dot: "bg-amber-500",
    description: "人工审批工具调用",
  },
  model_call_limit: {
    className: "ModelCallLimitMiddleware",
    label: "模型调用限制",
    icon: Gauge,
    color: "text-rose-600",
    bg: "bg-rose-50",
    border: "border-rose-200",
    dot: "bg-rose-500",
    description: "限制模型调用次数",
  },
  tool_call_limit: {
    className: "ToolCallLimitMiddleware",
    label: "工具调用限制",
    icon: Wrench,
    color: "text-orange-600",
    bg: "bg-orange-50",
    border: "border-orange-200",
    dot: "bg-orange-500",
    description: "限制工具调用次数",
  },
  model_fallback: {
    className: "ModelFallbackMiddleware",
    label: "模型回退",
    icon: Repeat,
    color: "text-cyan-600",
    bg: "bg-cyan-50",
    border: "border-cyan-200",
    dot: "bg-cyan-500",
    description: "模型失败时回退到备选模型",
  },
  pii: {
    className: "PIIMiddleware",
    label: "PII 脱敏",
    icon: ShieldAlert,
    color: "text-red-600",
    bg: "bg-red-50",
    border: "border-red-200",
    dot: "bg-red-500",
    description: "PII 检测和脱敏",
  },
  todo_list: {
    className: "TodoListMiddleware",
    label: "任务清单",
    icon: ListTodo,
    color: "text-blue-600",
    bg: "bg-blue-50",
    border: "border-blue-200",
    dot: "bg-blue-500",
    description: "任务规划和跟踪",
  },
  llm_tool_selector: {
    className: "LLMToolSelectorMiddleware",
    label: "LLM 工具选择",
    icon: MousePointerClick,
    color: "text-teal-600",
    bg: "bg-teal-50",
    border: "border-teal-200",
    dot: "bg-teal-500",
    description: "LLM 工具选择",
  },
  tool_retry: {
    className: "ToolRetryMiddleware",
    label: "工具重试",
    icon: RefreshCw,
    color: "text-yellow-600",
    bg: "bg-yellow-50",
    border: "border-yellow-200",
    dot: "bg-yellow-500",
    description: "工具调用失败自动重试",
  },
  llm_tool_emulator: {
    className: "LLMToolEmulator",
    label: "LLM 工具模拟",
    icon: Terminal,
    color: "text-slate-600",
    bg: "bg-slate-50",
    border: "border-slate-200",
    dot: "bg-slate-500",
    description: "LLM 工具模拟",
  },
  context_editing: {
    className: "ContextEditingMiddleware",
    label: "上下文编辑",
    icon: Edit3,
    color: "text-indigo-600",
    bg: "bg-indigo-50",
    border: "border-indigo-200",
    dot: "bg-indigo-500",
    description: "上下文编辑",
  },
  shell_tool: {
    className: "ShellToolMiddleware",
    label: "Shell 会话",
    icon: SquareTerminal,
    color: "text-zinc-600",
    bg: "bg-zinc-50",
    border: "border-zinc-200",
    dot: "bg-zinc-500",
    description: "Shell 会话",
  },
  filesystem_file_search: {
    className: "FilesystemFileSearchMiddleware",
    label: "文件搜索",
    icon: FolderSearch,
    color: "text-emerald-600",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    dot: "bg-emerald-500",
    description: "文件系统搜索",
  },
};

// 反向映射：用于旧数据（无 lc_source）通过 middleware_name 模糊匹配
const MW_KEYWORDS: Array<{ keyword: string; lcSource: string }> = Object.entries(
  MIDDLEWARE_CONF
).map(([lcSource, conf]) => ({
  // 去掉 "Middleware" 后缀作为关键词，小写
  keyword: conf.className.replace("Middleware", "").toLowerCase(),
  lcSource,
}));

/** 解析事件的 lc_source；优先用字段，缺失时通过 middleware_name 模糊匹配回填。 */
function resolveEventLcSource(event: TraceEvent): string | null {
  if (event.lc_source && event.lc_source in MIDDLEWARE_CONF) {
    return event.lc_source;
  }
  const name = event.middleware_name || event.node_name;
  if (name) {
    const nameLower = name.toLowerCase();
    for (const { keyword, lcSource } of MW_KEYWORDS) {
      if (keyword && nameLower.includes(keyword)) {
        return lcSource;
      }
    }
  }
  return null;
}

function getType(m: Message): string {
  // Middleware 注入的消息：additional_kwargs.lc_source 标识来源
  // 检查所有已知 middleware 类型，而非仅 summarization
  const lcSource = m.additional_kwargs?.lc_source;
  if (typeof lcSource === "string" && lcSource in MIDDLEWARE_CONF) {
    return lcSource;
  }
  return m.type ?? m._type ?? "unknown";
}

function getModelName(m: Message): string | undefined {
  return m.response_metadata?.model_name ?? m.response_metadata?.model;
}

function getContentText(content: unknown): string {
  if (typeof content === "string") return content;
  if (content == null) return "";
  try {
    return JSON.stringify(content, null, 2);
  } catch {
    return String(content);
  }
}

function fmtTime(ts?: string): string | null {
  if (!ts) return null;
  const d = new Date(ts);
  if (isNaN(d.getTime())) return null;
  return d.toLocaleTimeString("zh-CN", { hour12: false });
}

/**
 * 消息本身无时间字段，按类型从 events 顺序关联：
 * - human/system → trace 起始时间
 * - ai → 第 N 个 llm_end 事件时间
 * - tool → 第 N 个 tool_end 事件时间
 */
function buildMessageTimes(
  messages: Message[],
  events: TraceEvent[],
  startTime?: string | null
): (string | undefined)[] {
  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  const llmEnds = sorted.filter((e) => e.event_type === "llm_end");
  const toolEnds = sorted.filter((e) => e.event_type === "tool_end");
  const fallback = startTime ?? sorted[0]?.timestamp;
  let aiIdx = 0;
  let toolIdx = 0;
  return messages.map((m) => {
    const t = getType(m);
    if (t === "ai" || t === "AIMessage") return llmEnds[aiIdx++]?.timestamp;
    if (t === "tool" || t === "ToolMessage") return toolEnds[toolIdx++]?.timestamp;
    return fallback;
  });
}

const TYPE_CONF: Record<
  string,
  { label: string; dot: string; align: "left" | "right" | "center"; bg: string; border: string }
> = {
  human: { label: "用户", dot: "bg-blue-500", align: "right", bg: "bg-blue-50", border: "border-blue-200" },
  HumanMessage: { label: "用户", dot: "bg-blue-500", align: "right", bg: "bg-blue-50", border: "border-blue-200" },
  ai: { label: "AI", dot: "bg-indigo-500", align: "left", bg: "bg-white", border: "border-slate-200" },
  AIMessage: { label: "AI", dot: "bg-indigo-500", align: "left", bg: "bg-white", border: "border-slate-200" },
  tool: { label: "工具", dot: "bg-amber-500", align: "center", bg: "bg-amber-50", border: "border-amber-200" },
  ToolMessage: { label: "工具", dot: "bg-amber-500", align: "center", bg: "bg-amber-50", border: "border-amber-200" },
  system: { label: "系统", dot: "bg-slate-500", align: "center", bg: "bg-slate-50", border: "border-slate-200" },
  SystemMessage: { label: "系统", dot: "bg-slate-500", align: "center", bg: "bg-slate-50", border: "border-slate-200" },
  // 向后兼容：旧数据无 lc_source 字段时可能命中 "summary"
  summary: { label: "Summary (压缩)", dot: "bg-purple-500", align: "center", bg: "bg-purple-50", border: "border-purple-300" },
};

export default function MessageFlow({ messages, structuredResponse, events = [], startTime }: Props) {
  const msgs = (messages ?? []) as Message[];
  if (msgs.length === 0 && structuredResponse == null) {
    return (
      <div className="text-center py-12 text-slate-400">
        <p className="text-sm">无消息</p>
      </div>
    );
  }
  const justify = (a: "left" | "right" | "center") =>
    a === "right" ? "items-end" : a === "center" ? "items-center" : "items-start";
  const times = buildMessageTimes(msgs, events, startTime);

  // 找每条消息之前最近一个 middleware chain_start，渲染为横幅
  const sortedEvents = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  // 收集所有 middleware 触发的 chain_start 事件
  const middlewareStarts = sortedEvents.filter(
    (e) => e.is_middleware && e.event_type === "chain_start"
  );
  // 按 run_id 索引 middleware 事件，便于横幅拿 end 行为
  const mwByRun = new Map<string, { start?: TraceEvent; end?: TraceEvent }>();
  for (const e of sortedEvents) {
    if (!e.is_middleware) continue;
    if (e.event_type !== "chain_start" && e.event_type !== "chain_end") continue;
    const slot = mwByRun.get(e.run_id) ?? {};
    if (e.event_type === "chain_start") slot.start = e;
    else slot.end = e;
    mwByRun.set(e.run_id, slot);
  }

  /** 计算 middleware 行为描述：start 描述输入状态，end 描述输出影响 */
  function describeMw(mw: TraceEvent, kind: "start" | "end"): string | null {
    const lcSource = resolveEventLcSource(mw);
    const name = mw.middleware_name || mw.node_name || "";
    // 向后兼容：无 lc_source 时回退到 name 匹配
    const isPii = lcSource === "pii" || (!lcSource && name.includes("PII"));
    const isSummarization =
      lcSource === "summarization" || (!lcSource && name.includes("Summarization"));
    if (kind === "start") {
      if (isPii) {
        const text = JSON.stringify(mw.inputs ?? {});
        const email = (text.match(/[\w.-]+@[\w.-]+/g) || []).length;
        const phone = (text.match(/\b1[3-9]\d{9}\b/g) || []).length;
        const idCard = (text.match(/\b\d{17}[\dXx]\b/g) || []).length;
        if (email + phone + idCard > 0) {
          const parts: string[] = [];
          if (email) parts.push(`邮箱×${email}`);
          if (phone) parts.push(`手机×${phone}`);
          if (idCard) parts.push(`身份证×${idCard}`);
          return `检测到 ${parts.join("、")}`;
        }
        return "扫描中（未发现 PII）";
      }
      if (isSummarization) {
        const s = summarizeMessages((mw.inputs as { messages?: unknown } | undefined)?.messages);
        if (s) return `历史 ${s.count} 条 / ${s.chars} 字符`;
      }
      return null;
    } else {
      if (isPii) {
        const text = JSON.stringify(mw.outputs ?? {});
        const redacted = (text.match(/\[REDACTED_[A-Z_]+\]/g) || []).length;
        if (redacted > 0) return `脱敏 ${redacted} 处`;
        return "未脱敏";
      }
      if (isSummarization) {
        const s = summarizeMessages((mw.outputs as { messages?: unknown } | undefined)?.messages);
        if (s) return `压缩后 ${s.count} 条 / ${s.chars} 字符`;
      }
      return null;
    }
  }

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

  return (
    <div className="space-y-4">
      <div className={`flex flex-col gap-3`}>
        {msgs.map((m, i) => {
          const t = getType(m);
          // middleware 注入的消息优先用 MIDDLEWARE_CONF，否则用 TYPE_CONF
          const mwConf = MIDDLEWARE_CONF[t];
          const conf = mwConf
            ? {
                label: mwConf.label,
                dot: mwConf.dot,
                align: "center" as const,
                bg: mwConf.bg,
                border: mwConf.border,
              }
            : TYPE_CONF[t] ?? {
                label: t,
                dot: "bg-slate-400",
                align: "left" as const,
                bg: "bg-white",
                border: "border-slate-200",
              };
          const text = getContentText(m.content);
          const isAI = t === "ai" || t === "AIMessage";
          // AI 显示模型名（类似 tool 显示工具名）
          const subName = isAI ? getModelName(m) : m.name;
          // middleware 注入的消息
          const isMwMessage = !!mwConf;
          const time = fmtTime(times[i]);
          // 该消息时间之前最近的 middleware
          const msgTs = times[i] ? new Date(times[i]!).getTime() : null;
          const precedingMiddleware = msgTs
            ? middlewareStarts.filter(
                (mw) => new Date(mw.timestamp).getTime() <= msgTs
              )
            : [];
          return (
            <Fragment key={m.id ?? i}>
              {/* 中间件边界横幅 */}
              {precedingMiddleware.map((mw) => {
                const slot = mwByRun.get(mw.run_id);
                const endEv = slot?.end;
                const startHint = describeMw(mw, "start");
                const endHint = endEv ? describeMw(endEv, "end") : null;
                // 按 lc_source 查配置；未知 middleware 回退到默认橙色
                const mwLcSource = resolveEventLcSource(mw);
                const mwCfg = mwLcSource ? MIDDLEWARE_CONF[mwLcSource] : null;
                const bannerBg = mwCfg?.bg ?? "bg-orange-50";
                const bannerBorder = mwCfg?.border ?? "border-orange-200";
                const bannerText = mwCfg?.color ?? "text-orange-800";
                const BannerIcon = mwCfg?.icon ?? Settings2;
                const displayName = mwCfg?.className ?? mw.middleware_name ?? mw.node_name ?? "Middleware";
                return (
                  <div
                    key={`mw-${mw.event_id}`}
                    className={`my-1.5 px-3 py-2 rounded-md ${bannerBg} ${bannerBorder} text-xs ${bannerText} border`}
                  >
                    <div className="flex items-center gap-2 flex-wrap">
                      <BannerIcon className="w-3.5 h-3.5 shrink-0" />
                      <span className="font-semibold">{displayName}</span>
                      {mw.node_name && mw.node_name !== displayName && (
                        <span className="opacity-70 mono">({mw.node_name})</span>
                      )}
                      {startHint && (
                        <span className="mono opacity-80">· {startHint}</span>
                      )}
                      {endHint && (
                        <>
                          <span className="opacity-60">→</span>
                          <span className="mono font-medium">{endHint}</span>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
              <div className={`flex flex-col ${justify(conf.align)}`}>
                <div className="flex items-center gap-1.5 mb-1 px-0.5">
                  <span className={`w-1.5 h-1.5 rounded-full ${conf.dot}`} />
                  {isMwMessage && mwConf && (
                    <mwConf.icon className={`w-3 h-3 ${mwConf.color}`} />
                  )}
                  <span className="text-[11px] font-medium text-slate-500">
                    {conf.label}
                    {subName ? ` · ${subName}` : ""}
                  </span>
                  {isMwMessage && mwConf && (
                    <span
                      className={`text-[10px] mono px-1.5 py-0.5 rounded ${mwConf.bg} ${mwConf.color} border ${mwConf.border}`}
                    >
                      by {mwConf.className}
                    </span>
                  )}
                  {time && (
                    <span className="inline-flex items-center gap-0.5 ml-1 text-[10px] text-slate-400 mono">
                      <Clock className="w-2.5 h-2.5" />
                      {time}
                    </span>
                  )}
                </div>
                <div className={`max-w-[80%] rounded-lg ${conf.bg} ${conf.border} border px-3.5 py-2.5`}>
                  {text && (
                    <div className="markdown-body text-sm text-slate-700 leading-relaxed">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeHighlight]}>
                        {text}
                      </ReactMarkdown>
                    </div>
                  )}
                  {m.tool_calls && m.tool_calls.length > 0 && (
                    <div className="mt-2 pt-2 border-t border-slate-200/70 space-y-1">
                      {m.tool_calls.map((tc, j) => (
                        <div key={j} className="flex items-start gap-1.5 text-xs text-amber-800">
                          <Wrench className="w-3.5 h-3.5 mt-0.5 shrink-0 text-amber-600" />
                          <div className="min-w-0">
                            <span className="font-medium">{tc.name}</span>
                            <pre className="mt-0.5 text-[11px] mono text-amber-900/80 overflow-auto">
                              {(() => {
                                try {
                                  return JSON.stringify(tc.args, null, 2);
                                } catch {
                                  return String(tc.args);
                                }
                              })()}
                            </pre>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </Fragment>
          );
        })}
      </div>

      {structuredResponse != null && (
        <div className="mt-4 rounded-lg border border-purple-200 bg-purple-50/60 p-3.5">
          <div className="text-xs font-semibold text-purple-700 mb-1.5 uppercase tracking-wide">
            结构化响应
          </div>
          <pre className="text-xs mono text-purple-900/90 overflow-auto leading-relaxed">
            {(() => {
              try {
                return JSON.stringify(structuredResponse, null, 2);
              } catch {
                return String(structuredResponse);
              }
            })()}
          </pre>
        </div>
      )}
    </div>
  );
}
