"""Trace 模型。"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.event import Event


class TraceStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TraceCreate(BaseModel):
    """创建 trace 的请求体。"""

    name: str | None = None
    # 会话分组 ID（LangGraph 的 configurable.thread_id）
    thread_id: str | None = None
    input: Any | None = None
    output: Any | None = None
    messages: list[Any] = Field(default_factory=list)
    structured_response: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: TraceStatus = TraceStatus.SUCCEEDED
    error: dict[str, Any] | None = None
    events: list[Event] = Field(default_factory=list)


class Trace(TraceCreate):
    """完整 trace（含 ID）。"""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    duration_ms: int | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.start_time and self.end_time and self.duration_ms is None:
            delta = self.end_time - self.start_time
            self.duration_ms = int(delta.total_seconds() * 1000)
