"""服务层测试。"""
import pytest

from app.models import TraceCreate
from app.repositories.memory import InMemoryRepository
from app.services import TraceService


@pytest.fixture
def service():
    return TraceService(InMemoryRepository())


async def test_create_and_get(service):
    t = await service.create_trace(TraceCreate(name="svc"))
    assert await service.get_trace(t.trace_id) is not None


async def test_list_and_count(service):
    await service.create_trace(TraceCreate(name="a"))
    await service.create_trace(TraceCreate(name="b"))
    assert await service.count_traces() == 2
    assert len(await service.list_traces()) == 2


async def test_delete(service):
    t = await service.create_trace(TraceCreate(name="x"))
    assert await service.delete_trace(t.trace_id) is True
    assert await service.get_trace(t.trace_id) is None
