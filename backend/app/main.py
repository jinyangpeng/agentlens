"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings
from app.dependencies import init_storage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化存储后端（数据库自动建表）
    await init_storage()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="AgentLens Server",
        version="0.5.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
