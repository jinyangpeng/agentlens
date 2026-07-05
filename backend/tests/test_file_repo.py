"""文件仓储测试。"""
import pytest

from app.models import TraceCreate
from app.repositories.file import FileRepository


@pytest.fixture
def repo(tmp_path):
    return FileRepository(str(tmp_path / "traces"))


async def test_create_and_get(repo):
    created = await repo.create(TraceCreate(name="file-test"))
    fetched = await repo.get(created.trace_id)
    assert fetched is not None
    assert fetched.name == "file-test"


async def test_list_order(repo):
    """同 thread_id 按 start_time 倒序；无 thread_id 在后。"""
    from datetime import datetime, timezone
    a = await repo.create(TraceCreate(
        name="a", thread_id="t1",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ))
    b = await repo.create(TraceCreate(
        name="b", thread_id="t1",
        start_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
    ))
    c = await repo.create(TraceCreate(name="c"))  # 无 thread_id
    result = await repo.list(limit=10)
    # b 比 a 新 → b 在前；c 无 thread_id 排最后
    assert result[0].name == "b"
    assert result[1].name == "a"
    assert result[2].name == "c"


async def test_list_filter_by_thread(repo):
    """按 thread_id 筛选。"""
    from datetime import datetime, timezone
    await repo.create(TraceCreate(
        name="a", thread_id="t1",
        start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
    ))
    await repo.create(TraceCreate(
        name="b", thread_id="t2",
        start_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
    ))
    result = await repo.list(limit=10, thread_id="t1")
    assert len(result) == 1
    assert result[0].name == "a"


async def test_count_and_delete(repo):
    await repo.create(TraceCreate(name="x"))
    assert await repo.count() == 1
    files = list(repo._dir.glob("*.json"))
    await repo.delete(files[0].stem)
    assert await repo.count() == 0
