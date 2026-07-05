"""JSON 文件存储实现。每个 trace 存为一个 JSON 文件。"""
from __future__ import annotations  # 延迟求值注解，规避循环 import 时的求值失败

import json
from pathlib import Path

from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


class FileRepository(TraceRepository):
    """文件存储。每个 trace 一个 .json 文件，按 thread_id + 时间排序读取列表。"""

    def __init__(self, storage_dir: str) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, trace_id: str) -> Path:
        return self._dir / f"{trace_id}.json"

    async def create(self, trace_create: TraceCreate) -> Trace:
        trace = Trace(**trace_create.model_dump())
        self._path(trace.trace_id).write_text(
            trace.model_dump_json(indent=2), encoding="utf-8"
        )
        return trace

    async def get(self, trace_id: str) -> Trace | None:
        p = self._path(trace_id)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return Trace(**data)

    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        thread_id: str | None = None,
    ) -> list[Trace]:
        traces: list[Trace] = []
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                traces.append(Trace(**data))
            except Exception:
                continue
        if thread_id:
            traces = [t for t in traces if t.thread_id == thread_id]
        traces.sort(
            key=lambda t: (
                0 if t.thread_id else 1,
                t.thread_id or "",
                -(t.start_time.timestamp() if t.start_time else 0),
            )
        )
        return traces[offset : offset + limit]

    async def count(self) -> int:
        return len(list(self._dir.glob("*.json")))

    async def list_by_thread(self, thread_id: str) -> list[Trace]:
        traces: list[Trace] = []
        for f in self._dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                t = Trace(**data)
                if t.thread_id == thread_id:
                    traces.append(t)
            except Exception:
                continue
        traces.sort(
            key=lambda t: t.start_time.timestamp() if t.start_time else 0
        )
        return traces

    async def delete(self, trace_id: str) -> bool:
        p = self._path(trace_id)
        if p.exists():
            p.unlink()
            return True
        return False
