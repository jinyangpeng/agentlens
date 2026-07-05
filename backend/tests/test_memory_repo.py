"""内存仓储测试。"""
import pytest

from app.models import Event, EventType, TraceCreate
from app.repositories.memory import InMemoryRepository


@pytest.fixture
def repo():
    return InMemoryRepository()


async def test_create_and_get(repo):
    tc = TraceCreate(name="test", input={"q": "hi"})
    created = await repo.create(tc)
    assert created.trace_id
    fetched = await repo.get(created.trace_id)
    assert fetched is not None
    assert fetched.name == "test"


async def test_get_not_found(repo):
    assert await repo.get("missing") is None


async def test_list_pagination(repo):
    for i in range(5):
        await repo.create(TraceCreate(name=f"t{i}"))
    page = await repo.list(limit=2, offset=0)
    assert len(page) == 2
    assert page[0].name == "t0"
    page2 = await repo.list(limit=2, offset=2)
    assert page2[0].name == "t2"


async def test_count(repo):
    await repo.create(TraceCreate(name="a"))
    await repo.create(TraceCreate(name="b"))
    assert await repo.count() == 2


async def test_delete(repo):
    created = await repo.create(TraceCreate(name="x"))
    assert await repo.delete(created.trace_id) is True
    assert await repo.get(created.trace_id) is None
    assert await repo.delete("missing") is False


async def test_create_with_events(repo):
    e = Event(run_id="r1", event_type=EventType.CHAIN_START)
    tc = TraceCreate(name="with-events", events=[e])
    created = await repo.create(tc)
    fetched = await repo.get(created.trace_id)
    assert len(fetched.events) == 1
