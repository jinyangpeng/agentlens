"""Trace API 端点。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_trace_service
from app.models.trace import Trace, TraceCreate
from app.services import TraceService

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("", response_model=Trace, status_code=201)
async def create_trace(
    payload: TraceCreate,
    service: TraceService = Depends(get_trace_service),
) -> Trace:
    """接收一个完整 trace（含事件），保存。"""
    return await service.create_trace(payload)


@router.get("", response_model=list[Trace])
async def list_traces(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    thread_id: str | None = Query(None, description="按会话 thread_id 筛选"),
    service: TraceService = Depends(get_trace_service),
) -> list[Trace]:
    """分页列出 trace（含 events）。按 thread_id 分组排序，同会话相邻。"""
    return await service.list_traces(limit=limit, offset=offset, thread_id=thread_id)


@router.get("/by_thread/{thread_id}", response_model=list[Trace])
async def list_by_thread(
    thread_id: str,
    service: TraceService = Depends(get_trace_service),
) -> list[Trace]:
    """返回指定会话的全部 trace（按 start_time 升序，用于会话详情连贯展示）。"""
    return await service.list_by_thread(thread_id)


@router.get("/count/total")
async def count_traces(
    service: TraceService = Depends(get_trace_service),
) -> dict:
    """获取 trace 总数。"""
    return {"count": await service.count_traces()}


@router.get("/{trace_id}", response_model=Trace)
async def get_trace(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> Trace:
    """获取单个 trace 详情（含全部事件）。"""
    trace = await service.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace


@router.delete("/{trace_id}", status_code=204)
async def delete_trace(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> None:
    """删除 trace。"""
    ok = await service.delete_trace(trace_id)
    if not ok:
        raise HTTPException(status_code=404, detail="trace not found")
