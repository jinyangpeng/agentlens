"""SQLAlchemy ORM 模型。使用 2.0 风格（DeclarativeBase + Mapped）。"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """ORM 声明基类。"""


class TraceModel(Base):
    """trace 表。一个 trace 对应一次 agent 运行记录。"""

    __tablename__ = "traces"

    trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # 会话分组 ID（LangGraph 的 configurable.thread_id），建索引用于按会话查询
    thread_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    input: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    output: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    messages: Mapped[Any | None] = mapped_column(JSON, nullable=True, default=list)
    structured_response: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Any | None] = mapped_column("metadata", JSON, nullable=True, default=dict)
    tags: Mapped[Any | None] = mapped_column(JSON, nullable=True, default=list)
    start_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="succeeded")
    error: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    events: Mapped[list[EventModel]] = relationship(
        "EventModel",
        back_populates="trace",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class EventModel(Base):
    """event 表。一个 trace 可包含多个回调事件。"""

    __tablename__ = "events"

    event_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    trace_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("traces.trace_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    parent_run_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    serialized: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    inputs: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    outputs: Mapped[Any | None] = mapped_column(JSON, nullable=True)
    metadata_: Mapped[Any | None] = mapped_column("metadata", JSON, nullable=True, default=dict)
    tags: Mapped[Any | None] = mapped_column(JSON, nullable=True, default=list)
    level: Mapped[str] = mapped_column(String(32), default="info", nullable=False)
    is_middleware: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    middleware_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    node_name: Mapped[str | None] = mapped_column(String(256), nullable=True)

    trace: Mapped[TraceModel] = relationship("TraceModel", back_populates="events")
