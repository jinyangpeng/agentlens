"""仓储抽象基类。扩展存储后端时继承此类并实现所有方法。"""
from __future__ import annotations  # 延迟求值注解，避免循环 import 时 list[Trace] 解析失败

from abc import ABC, abstractmethod

from app.models.trace import Trace, TraceCreate


class TraceRepository(ABC):
    """Trace 存储仓储接口。"""

    @abstractmethod
    async def create(self, trace_create: TraceCreate) -> Trace:
        """创建 trace。"""

    @abstractmethod
    async def get(self, trace_id: str) -> Trace | None:
        """按 ID 获取 trace（含 events）。"""

    @abstractmethod
    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        thread_id: str | None = None,
    ) -> list[Trace]:
        """分页列出 trace（不含 events，仅摘要）。

        thread_id 非空时按会话筛选；为空时按 thread_id 分组排序（同会话相邻，无 thread_id 在后）。
        """

    @abstractmethod
    async def list_by_thread(self, thread_id: str) -> list[Trace]:
        """返回指定会话的全部 trace（按 start_time 升序，连贯展示用）。"""

    @abstractmethod
    async def count(self) -> int:
        """trace 总数。"""

    @abstractmethod
    async def delete(self, trace_id: str) -> bool:
        """删除 trace，返回是否删除成功。"""
