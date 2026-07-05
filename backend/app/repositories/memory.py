"""内存存储实现（默认）。"""
from __future__ import annotations  # 延迟求值注解，规避循环 import 时的求值失败

from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


class InMemoryRepository(TraceRepository):
    """线程安全的内存存储。适用于开发与单实例部署。"""

    def __init__(self) -> None:
        self._store: dict[str, Trace] = {}

    async def create(self, trace_create: TraceCreate) -> Trace:
        trace = Trace(**trace_create.model_dump())
        self._store[trace.trace_id] = trace
        return trace

    async def get(self, trace_id: str) -> Trace | None:
        return self._store.get(trace_id)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        thread_id: str | None = None,
    ) -> list[Trace]:
        traces = list(self._store.values())
        if thread_id:
            traces = [t for t in traces if t.thread_id == thread_id]
        # 排序：有 thread_id 在前 → 同 thread_id 相邻 → 组内 start_time 倒序（新的在前）
        traces.sort(
            key=lambda t: (
                0 if t.thread_id else 1,
                t.thread_id or "",
                -(t.start_time.timestamp() if t.start_time else 0),
            )
        )
        return traces[offset : offset + limit]

    async def count(self) -> int:
        return len(self._store)

    async def list_by_thread(self, thread_id: str) -> list[Trace]:
        traces = [t for t in self._store.values() if t.thread_id == thread_id]
        traces.sort(
            key=lambda t: t.start_time.timestamp() if t.start_time else 0
        )
        return traces

    async def delete(self, trace_id: str) -> bool:
        if trace_id in self._store:
            del self._store[trace_id]
            return True
        return False
