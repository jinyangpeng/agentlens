"""统计 API 端点。"""
from datetime import date

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_stats_service
from app.services.stats_service import (
    Dimension,
    OverviewResponse,
    StatsService,
    TokenStatsResponse,
)

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/tokens", response_model=TokenStatsResponse)
async def token_stats(
    dimension: Dimension = Query(
        "session", description="统计维度：session | user | app"
    ),
    start_date: date | None = Query(None, description="起始日期（含），YYYY-MM-DD"),
    end_date: date | None = Query(None, description="结束日期（含），YYYY-MM-DD"),
    service: StatsService = Depends(get_stats_service),
) -> TokenStatsResponse:
    """按维度聚合 token 用量，返回分组明细与总计。"""
    return await service.get_token_stats(
        dimension=dimension, start_date=start_date, end_date=end_date
    )


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    service: StatsService = Depends(get_stats_service),
) -> OverviewResponse:
    """返回总体概览指标。"""
    return await service.get_overview()
