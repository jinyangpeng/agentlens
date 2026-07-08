"""SQLAlchemy 异步仓储实现。支持 SQLite（aiosqlite）与 PostgreSQL（asyncpg）。"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from sqlalchemy import case, delete, func, or_, select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import noload

from app.models.db import Base, EventModel, TraceModel
from app.models.event import Event
from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


# ----------------------------- 模型转换函数 -----------------------------


def _event_to_orm(event: Event) -> EventModel:
    """将 Pydantic Event 转为 ORM EventModel（trace_id 由关系回填）。"""
    return EventModel(
        event_id=event.event_id,
        run_id=event.run_id,
        parent_run_id=event.parent_run_id,
        event_type=event.event_type.value,
        timestamp=event.timestamp,
        name=event.name,
        serialized=event.serialized,
        inputs=event.inputs,
        outputs=event.outputs,
        metadata_=event.metadata,
        tags=event.tags,
        level=event.level,
        is_middleware=event.is_middleware,
        middleware_name=event.middleware_name,
        node_name=event.node_name,
    )


def _trace_to_orm(trace: Trace) -> TraceModel:
    """将 Pydantic Trace 转为 ORM TraceModel（含 events 关系）。"""
    return TraceModel(
        trace_id=trace.trace_id,
        name=trace.name,
        thread_id=trace.thread_id,
        input=trace.input,
        output=trace.output,
        messages=trace.messages,
        structured_response=trace.structured_response,
        metadata_=trace.metadata,
        tags=trace.tags,
        start_time=trace.start_time,
        end_time=trace.end_time,
        status=trace.status.value if trace.status else "succeeded",
        error=trace.error,
        duration_ms=trace.duration_ms,
        events=[_event_to_orm(e) for e in trace.events],
    )


def _orm_to_event(row: EventModel) -> Event:
    """将 ORM EventModel 转为 Pydantic Event。"""
    return Event(
        event_id=row.event_id,
        run_id=row.run_id,
        parent_run_id=row.parent_run_id,
        event_type=row.event_type,
        timestamp=row.timestamp,
        name=row.name,
        serialized=row.serialized,
        inputs=row.inputs,
        outputs=row.outputs,
        metadata=row.metadata_ or {},
        tags=row.tags or [],
        level=row.level,
        is_middleware=row.is_middleware,
        middleware_name=row.middleware_name,
        node_name=row.node_name,
    )


def _orm_to_trace(row: TraceModel, include_events: bool = True) -> Trace:
    """将 ORM TraceModel 转为 Pydantic Trace。

    include_events=False 时仅返回摘要（用于 list，避免加载事件）。
    """
    events: list[Event] = []
    if include_events and row.events:
        events = [_orm_to_event(e) for e in row.events]
    return Trace(
        trace_id=row.trace_id,
        name=row.name,
        thread_id=row.thread_id,
        input=row.input,
        output=row.output,
        messages=row.messages or [],
        structured_response=row.structured_response,
        metadata=row.metadata_ or {},
        tags=row.tags or [],
        start_time=row.start_time,
        end_time=row.end_time,
        status=row.status,
        error=row.error,
        duration_ms=row.duration_ms,
        events=events,
    )


# ----------------------------- 仓储实现 -----------------------------


class SQLAlchemyRepository(TraceRepository):
    """SQLAlchemy 异步仓储。默认建表后即可使用。"""

    def __init__(self, database_url: str) -> None:
        self._database_url = database_url
        self._engine = create_async_engine(database_url, echo=False, future=True)
        self._sessionmaker = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self) -> None:
        """创建所有表（幂等）。SQLite 时自动创建父目录。"""
        url = make_url(self._database_url)
        if url.drivername.startswith("sqlite"):
            db_path = url.database
            if db_path:
                Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def close(self) -> None:
        """释放引擎资源。"""
        await self._engine.dispose()

    async def create(self, trace_create: TraceCreate) -> Trace:
        """创建 trace（在同一事务中批量写入 trace + events）。"""
        trace = Trace(**trace_create.model_dump())
        orm = _trace_to_orm(trace)
        async with self._sessionmaker() as session:
            async with session.begin():
                session.add(orm)
        return trace

    async def get(self, trace_id: str) -> Trace | None:
        """按 ID 获取 trace（含 events，selectin 自动加载）。"""
        async with self._sessionmaker() as session:
            stmt = select(TraceModel).where(TraceModel.trace_id == trace_id)
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return _orm_to_trace(row, include_events=True)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        thread_id: str | None = None,
    ) -> list[Trace]:
        """分页列出 trace（不含 events）。

        排序逻辑复刻 file.py：
        - 有 thread_id 在前 → 同 thread_id 相邻 → 组内 start_time 倒序（新的在前）。
        """
        async with self._sessionmaker() as session:
            stmt = select(TraceModel).options(noload(TraceModel.events))
            if thread_id:
                stmt = stmt.where(TraceModel.thread_id == thread_id)
            # 第 1 键：无 thread_id（NULL 或空串）排到末尾
            thread_group = case(
                (or_(TraceModel.thread_id.is_(None), TraceModel.thread_id == ""), 1),
                else_=0,
            )
            # 第 2 键：thread_id 字典序（NULL 视作空串）
            thread_key = func.coalesce(TraceModel.thread_id, "")
            # 第 3/4 键：start_time 为 NULL 视作最早（排在组内最后），其余倒序
            start_null = case((TraceModel.start_time.is_(None), 1), else_=0)
            stmt = stmt.order_by(
                thread_group.asc(),
                thread_key.asc(),
                start_null.asc(),
                TraceModel.start_time.desc(),
            ).limit(limit).offset(offset)
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_orm_to_trace(r, include_events=False) for r in rows]

    async def list_by_thread(self, thread_id: str) -> list[Trace]:
        """返回指定会话的全部 trace（按 start_time 升序，NULL 视作最早）。"""
        async with self._sessionmaker() as session:
            start_null = case((TraceModel.start_time.is_(None), 0), else_=1)
            stmt = (
                select(TraceModel)
                .options(noload(TraceModel.events))
                .where(TraceModel.thread_id == thread_id)
                .order_by(start_null.asc(), TraceModel.start_time.asc())
            )
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [_orm_to_trace(r, include_events=False) for r in rows]

    async def count(self) -> int:
        async with self._sessionmaker() as session:
            result = await session.execute(
                select(func.count()).select_from(TraceModel)
            )
            return int(result.scalar_one())

    async def delete(self, trace_id: str) -> bool:
        """删除 trace（连同 events 一起删除）。返回是否删除成功。"""
        async with self._sessionmaker() as session:
            async with session.begin():
                # 显式删除事件，避免依赖数据库外键级联（SQLite 默认未开启 FK）
                await session.execute(
                    delete(EventModel).where(EventModel.trace_id == trace_id)
                )
                result = await session.execute(
                    delete(TraceModel).where(TraceModel.trace_id == trace_id)
                )
        return (result.rowcount or 0) > 0
