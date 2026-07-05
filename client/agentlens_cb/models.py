"""事件/trace 序列化模型（与后端 schema 对齐）。"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventPayload(BaseModel):
    """回调事件载荷。"""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    parent_run_id: str | None = None
    event_type: str
    timestamp: str = Field(default_factory=_now_iso)
    name: str | None = None
    serialized: dict[str, Any] | None = None
    inputs: Any | None = None
    outputs: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    level: str = "info"
    # Middleware 识别（启发式填充，便于前端直接读取）
    is_middleware: bool = False
    middleware_name: str | None = None
    node_name: str | None = None  # LangGraph node 名（来自 metadata.langgraph_node）


class TracePayload(BaseModel):
    """完整 trace 载荷。"""

    name: str | None = None
    # 会话分组 ID（LangGraph 的 configurable.thread_id）
    thread_id: str | None = None
    input: Any | None = None
    output: Any | None = None
    messages: list[Any] = Field(default_factory=list)
    structured_response: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    status: str = "succeeded"
    error: dict[str, Any] | None = None
    events: list[EventPayload] = Field(default_factory=list)
