"""FastAPI 依赖注入。"""
from functools import lru_cache

from app.config import settings
from app.repositories.base import TraceRepository
from app.repositories.memory import InMemoryRepository
from app.repositories.file import FileRepository
from app.services import TraceService


@lru_cache
def get_repository() -> TraceRepository:
    """根据配置返回存储仓储单例。"""
    if settings.storage_backend == "file":
        return FileRepository(settings.file_storage_dir)
    return InMemoryRepository()


def get_trace_service() -> TraceService:
    return TraceService(get_repository())
