"""Trace 业务逻辑层，封装仓储调用。"""
from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


class TraceService:
    """Trace 业务服务。"""

    def __init__(self, repository: TraceRepository) -> None:
        self._repo = repository

    async def create_trace(self, payload: TraceCreate) -> Trace:
        return await self._repo.create(payload)

    async def get_trace(self, trace_id: str) -> Trace | None:
        return await self._repo.get(trace_id)

    async def list_traces(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        thread_id: str | None = None,
    ) -> list[Trace]:
        return await self._repo.list(limit=limit, offset=offset, thread_id=thread_id)

    async def list_by_thread(self, thread_id: str) -> list[Trace]:
        """返回指定会话的全部 trace（按时间升序，用于会话详情连贯展示）。"""
        return await self._repo.list_by_thread(thread_id)

    async def count_traces(self) -> int:
        return await self._repo.count()

    async def delete_trace(self, trace_id: str) -> bool:
        return await self._repo.delete(trace_id)
