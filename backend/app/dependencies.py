"""FastAPI 依赖注入。"""
from functools import lru_cache

from app.config import settings
from app.repositories.base import TraceRepository
from app.repositories.memory import InMemoryRepository
from app.repositories.file import FileRepository
from app.repositories.sqlalchemy_repo import SQLAlchemyRepository
from app.services import StatsService, TraceService


@lru_cache
def get_repository() -> TraceRepository:
    """根据配置返回存储仓储单例。"""
    backend = settings.storage_backend
    if backend == "file":
        return FileRepository(settings.file_storage_dir)
    if backend in ("sqlite", "postgresql"):
        return SQLAlchemyRepository(settings.database_url)
    return InMemoryRepository()


async def init_storage() -> None:
    """异步初始化存储后端（数据库自动建表）。在应用 lifespan 中调用。"""
    repo = get_repository()
    if isinstance(repo, SQLAlchemyRepository):
        await repo.init_db()


def get_trace_service() -> TraceService:
    return TraceService(get_repository())


def get_stats_service() -> StatsService:
    return StatsService(get_repository())
