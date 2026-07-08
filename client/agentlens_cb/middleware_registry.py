"""LangChain v1.3.11 内置 AgentMiddleware 注册表。

定义 13 个内置 middleware 的标准属性，供前后端共享：
- lc_source: 标准化标识符（前后端通信用）
- display_name: UI 显示名
- icon: lucide-react 图标名（前端按此查找组件）
- color: Tailwind 颜色名（如 "purple"）
- description: 简短描述

检测策略：
1. 精确匹配类名（BUILTIN_MIDDLEWARES）
2. 模糊匹配：类名包含去掉 "Middleware" 后缀的关键词
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MiddlewareMeta:
    """中间件元数据（用于 UI 显示）。"""

    class_name: str  # 标准类名，如 "SummarizationMiddleware"
    lc_source: str  # 标准化标识符，如 "summarization", "pii"
    display_name: str  # UI 显示名，如 "摘要压缩", "PII 脱敏"
    icon: str  # 图标名（lucide-react 图标名）
    color: str  # Tailwind 颜色，如 "purple", "orange"
    description: str  # 简短描述


# 注册表：标准类名 -> MiddlewareMeta
BUILTIN_MIDDLEWARES: dict[str, MiddlewareMeta] = {
    "SummarizationMiddleware": MiddlewareMeta(
        class_name="SummarizationMiddleware",
        lc_source="summarization",
        display_name="摘要压缩",
        icon="FileText",
        color="purple",
        description="自动摘要历史消息",
    ),
    "HumanInTheLoopMiddleware": MiddlewareMeta(
        class_name="HumanInTheLoopMiddleware",
        lc_source="human_in_the_loop",
        display_name="人工审批",
        icon="UserCheck",
        color="amber",
        description="人工审批工具调用",
    ),
    "ModelCallLimitMiddleware": MiddlewareMeta(
        class_name="ModelCallLimitMiddleware",
        lc_source="model_call_limit",
        display_name="模型调用限制",
        icon="Gauge",
        color="rose",
        description="限制模型调用次数",
    ),
    "ToolCallLimitMiddleware": MiddlewareMeta(
        class_name="ToolCallLimitMiddleware",
        lc_source="tool_call_limit",
        display_name="工具调用限制",
        icon="Wrench",
        color="orange",
        description="限制工具调用次数",
    ),
    "ModelFallbackMiddleware": MiddlewareMeta(
        class_name="ModelFallbackMiddleware",
        lc_source="model_fallback",
        display_name="模型回退",
        icon="Repeat",
        color="cyan",
        description="模型失败时回退到备选模型",
    ),
    "PIIMiddleware": MiddlewareMeta(
        class_name="PIIMiddleware",
        lc_source="pii",
        display_name="PII 脱敏",
        icon="ShieldAlert",
        color="red",
        description="PII 检测和脱敏",
    ),
    "TodoListMiddleware": MiddlewareMeta(
        class_name="TodoListMiddleware",
        lc_source="todo_list",
        display_name="任务清单",
        icon="ListTodo",
        color="blue",
        description="任务规划和跟踪",
    ),
    "LLMToolSelectorMiddleware": MiddlewareMeta(
        class_name="LLMToolSelectorMiddleware",
        lc_source="llm_tool_selector",
        display_name="LLM 工具选择",
        icon="MousePointerClick",
        color="teal",
        description="LLM 工具选择",
    ),
    "ToolRetryMiddleware": MiddlewareMeta(
        class_name="ToolRetryMiddleware",
        lc_source="tool_retry",
        display_name="工具重试",
        icon="RefreshCw",
        color="yellow",
        description="工具调用失败自动重试",
    ),
    "LLMToolEmulator": MiddlewareMeta(
        class_name="LLMToolEmulator",
        lc_source="llm_tool_emulator",
        display_name="LLM 工具模拟",
        icon="Terminal",
        color="slate",
        description="LLM 工具模拟",
    ),
    "ContextEditingMiddleware": MiddlewareMeta(
        class_name="ContextEditingMiddleware",
        lc_source="context_editing",
        display_name="上下文编辑",
        icon="Edit3",
        color="indigo",
        description="上下文编辑",
    ),
    "ShellToolMiddleware": MiddlewareMeta(
        class_name="ShellToolMiddleware",
        lc_source="shell_tool",
        display_name="Shell 会话",
        icon="SquareTerminal",
        color="zinc",
        description="Shell 会话",
    ),
    "FilesystemFileSearchMiddleware": MiddlewareMeta(
        class_name="FilesystemFileSearchMiddleware",
        lc_source="filesystem_file_search",
        display_name="文件搜索",
        icon="FolderSearch",
        color="emerald",
        description="文件系统搜索",
    ),
}

# lc_source -> MiddlewareMeta 的反向映射
LC_SOURCE_MAP: dict[str, MiddlewareMeta] = {
    m.lc_source: m for m in BUILTIN_MIDDLEWARES.values()
}


def detect_middleware_type(name: str | None) -> MiddlewareMeta | None:
    """通过类名检测 middleware 类型。

    匹配策略：
    1. 精确匹配标准类名
    2. 模糊匹配：name（小写）包含去掉 "Middleware" 后缀的关键词
       例如 "PIIMiddleware[custom].before_model" 会匹配到 "PIIMiddleware"

    Returns: MiddlewareMeta 或 None（未匹配到内置 middleware）
    """
    if not name:
        return None
    # 精确匹配
    if name in BUILTIN_MIDDLEWARES:
        return BUILTIN_MIDDLEWARES[name]
    # 模糊匹配（包含关键词）
    name_lower = name.lower()
    for key, meta in BUILTIN_MIDDLEWARES.items():
        key_short = key.replace("Middleware", "").lower()
        if key_short and key_short in name_lower:
            return meta
    return None


def resolve_lc_source(lc_source: str | None, middleware_name: str | None) -> str | None:
    """根据 lc_source / middleware_name 解析出标准 lc_source。

    优先用 lc_source；缺失时通过 middleware_name 反查。
    用于旧数据回填（无 lc_source 字段时通过 middleware_name 推断）。
    """
    if lc_source and lc_source in LC_SOURCE_MAP:
        return lc_source
    if middleware_name:
        meta = detect_middleware_type(middleware_name)
        if meta:
            return meta.lc_source
    return None
