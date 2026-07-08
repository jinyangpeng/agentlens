"""统计业务逻辑层，聚合 token 用量与总体概览指标。"""
from __future__ import annotations  # 延迟求值注解，规避循环 import 时的求值失败

from datetime import date, datetime, time
from typing import Any, Literal

from pydantic import BaseModel

from app.models.event import EventType
from app.models.trace import Trace, TraceStatus
from app.repositories.base import TraceRepository

# 统计维度：session 按 thread_id 分组、user 按 metadata.user_id 分组、app 按 name 分组
Dimension = Literal["session", "user", "app"]

# 未知分组的占位 key
_UNKNOWN = "(未知)"


# ----------------------------- 响应模型 -----------------------------


class TokenStatItem(BaseModel):
    """单个分组的 token 统计项。"""

    key: str
    label: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0


class TokenTotals(BaseModel):
    """token 聚合总计。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    call_count: int = 0


class TokenStatsResponse(BaseModel):
    """token 统计响应。"""

    dimension: Dimension
    items: list[TokenStatItem]
    totals: TokenTotals


class OverviewResponse(BaseModel):
    """总体概览响应。"""

    total_traces: int
    total_tokens: int
    total_sessions: int
    avg_tokens_per_trace: float
    success_rate: float


# ----------------------------- 服务 -----------------------------


class StatsService:
    """统计服务。注入 TraceRepository，从 trace 的 llm_end 事件中聚合 token 用量。"""

    def __init__(self, repository: TraceRepository) -> None:
        self._repo = repository

    async def get_token_stats(
        self,
        dimension: Dimension,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> TokenStatsResponse:
        """按维度聚合 token 用量，返回分组明细与总计。"""
        traces = await self._load_traces(start_date, end_date)
        groups: dict[str, TokenStatItem] = {}
        totals = TokenTotals()
        for trace in traces:
            key, label = self._resolve_group(trace, dimension)
            item = groups.setdefault(key, TokenStatItem(key=key, label=label))
            for ev in trace.events:
                if ev.event_type != EventType.LLM_END:
                    continue
                usage = _extract_token_usage(ev.outputs)
                if usage is None:
                    continue
                item.prompt_tokens += usage["prompt_tokens"]
                item.completion_tokens += usage["completion_tokens"]
                item.total_tokens += usage["total_tokens"]
                item.call_count += 1
                totals.prompt_tokens += usage["prompt_tokens"]
                totals.completion_tokens += usage["completion_tokens"]
                totals.total_tokens += usage["total_tokens"]
                totals.call_count += 1
        # 按 total_tokens 倒序，并列时按 key 升序保证稳定输出
        items = sorted(
            groups.values(),
            key=lambda it: (-it.total_tokens, it.key),
        )
        return TokenStatsResponse(dimension=dimension, items=items, totals=totals)

    async def get_overview(self) -> OverviewResponse:
        """返回总体概览指标（无日期过滤）。"""
        traces = await self._load_traces(None, None)
        total_traces = len(traces)
        total_tokens = 0
        sessions: set[str] = set()
        succeeded = 0
        for trace in traces:
            if trace.thread_id:
                sessions.add(trace.thread_id)
            if trace.status == TraceStatus.SUCCEEDED:
                succeeded += 1
            for ev in trace.events:
                if ev.event_type != EventType.LLM_END:
                    continue
                usage = _extract_token_usage(ev.outputs)
                if usage is None:
                    continue
                total_tokens += usage["total_tokens"]
        avg_tokens = (total_tokens / total_traces) if total_traces else 0.0
        success_rate = (succeeded / total_traces) if total_traces else 0.0
        return OverviewResponse(
            total_traces=total_traces,
            total_tokens=total_tokens,
            total_sessions=len(sessions),
            avg_tokens_per_trace=round(avg_tokens, 2),
            success_rate=round(success_rate, 4),
        )

    # ----------------------------- 内部工具 -----------------------------

    async def _load_traces(
        self, start_date: date | None, end_date: date | None
    ) -> list[Trace]:
        """加载（按 start_time 过滤后的）全部 trace，并确保 events 已加载。

        list 在 SQLAlchemy 实现中不返回 events，需按需用 get 补全；
        memory/file 实现已在 list 中携带 events，无需额外查询。
        """
        summaries = await self._repo.list(limit=100_000, offset=0)
        start_dt = _to_start_datetime(start_date)
        end_dt = _to_end_datetime(end_date)
        result: list[Trace] = []
        for t in summaries:
            if t.start_time is None:
                # 有日期过滤时无法定位，跳过；无过滤时保留
                if start_dt or end_dt:
                    continue
            else:
                st = _normalize_dt(t.start_time)
                if start_dt and st < start_dt:
                    continue
                if end_dt and st > end_dt:
                    continue
            if not t.events:
                full = await self._repo.get(t.trace_id)
                if full is not None:
                    t = full
            result.append(t)
        return result

    @staticmethod
    def _resolve_group(trace: Trace, dimension: Dimension) -> tuple[str, str]:
        """根据维度从 trace 提取分组 key 与展示标签。"""
        if dimension == "session":
            tid = trace.thread_id or _UNKNOWN
            return tid, f"会话 {tid}"
        if dimension == "user":
            uid = _extract_user_id(trace)
            return uid, f"用户 {uid}"
        # app：以 trace.name 作为应用名
        name = trace.name or _UNKNOWN
        return name, name


# ----------------------------- 模块级工具函数 -----------------------------


def _extract_token_usage(outputs: Any) -> dict[str, int] | None:
    """从 llm_end 事件的 outputs 中提取 token_usage。

    outputs 可能是 dict 或 LLMResult 对象；token_usage 可能位于
    llm_output.token_usage 或 llm_output.usage。
    """
    if outputs is None:
        return None
    llm_output = _get_field(outputs, "llm_output")
    if llm_output is None:
        return None
    token_usage = _get_field(llm_output, "token_usage")
    if token_usage is None:
        token_usage = _get_field(llm_output, "usage")
    if token_usage is None:
        return None
    prompt = _to_int(_get_field(token_usage, "prompt_tokens"))
    completion = _to_int(_get_field(token_usage, "completion_tokens"))
    total = _to_int(_get_field(token_usage, "total_tokens"))
    # total 缺失时用 prompt + completion 兜底
    if total == 0 and (prompt or completion):
        total = prompt + completion
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def _extract_user_id(trace: Trace) -> str:
    """从 trace.metadata 提取用户标识（user_id 优先，其次 user）。"""
    md = trace.metadata or {}
    return str(md.get("user_id") or md.get("user") or _UNKNOWN)


def _get_field(obj: Any, key: str) -> Any:
    """兼容 dict 与对象属性的取值。"""
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key, None)


def _to_int(value: Any) -> int:
    """安全转 int，非数值返回 0。"""
    if value is None:
        return 0
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _to_start_datetime(d: date | None) -> datetime | None:
    """起始日期 → 当天 00:00:00。"""
    if d is None:
        return None
    return datetime.combine(d, time.min)


def _to_end_datetime(d: date | None) -> datetime | None:
    """结束日期 → 当天 23:59:59.999999。"""
    if d is None:
        return None
    return datetime.combine(d, time.max)


def _normalize_dt(dt: datetime) -> datetime:
    """比较前去除 tzinfo，避免 aware/naive 混用抛 TypeError。"""
    if dt.tzinfo is not None:
        return dt.replace(tzinfo=None)
    return dt
