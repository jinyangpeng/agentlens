"""模型测试。"""
from datetime import datetime

from app.models import Event, EventType, Trace, TraceCreate, TraceStatus


def test_event_defaults():
    e = Event(run_id="r1", event_type=EventType.CHAIN_START)
    assert e.event_id
    assert e.level == "info"
    assert e.metadata == {}
    assert e.tags == []


def test_trace_create_defaults():
    t = TraceCreate()
    assert t.status == TraceStatus.SUCCEEDED
    assert t.events == []
    assert t.messages == []


def test_trace_duration_computed():
    start = datetime(2026, 7, 4, 10, 0, 0)
    end = datetime(2026, 7, 4, 10, 0, 2, 500000)
    t = Trace(start_time=start, end_time=end)
    assert t.duration_ms == 2500
    assert t.trace_id
