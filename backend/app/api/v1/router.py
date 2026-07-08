"""v1 路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import stats, traces

api_router = APIRouter()
api_router.include_router(traces.router)
api_router.include_router(stats.router)
