"""Callback handler 测试。"""
from unittest.mock import MagicMock
from uuid import uuid4

from agentlens_cb import TraceCallbackHandler
from agentlens_cb.models import TracePayload


def test_handler_collects_events_and_sends():
    mock_client = MagicMock()
    handler = TraceCallbackHandler(client=mock_client, name="test-agent")

    run_id = uuid4()
    handler.on_chain_start(
        serialized={"name": "agent"},
        inputs={"messages": [{"role": "user", "content": "hi"}]},
        run_id=run_id,
    )
    handler.on_chain_end(
        outputs={"messages": [], "structured_response": None},
        run_id=run_id,
    )

    assert mock_client.send.called
    payload: TracePayload = mock_client.send.call_args.args[0]
    assert payload.name == "test-agent"
    assert len(payload.events) == 2
    assert payload.events[0].event_type == "chain_start"
    assert payload.status == "succeeded"


def test_handler_records_error():
    mock_client = MagicMock()
    handler = TraceCallbackHandler(client=mock_client)

    run_id = uuid4()
    handler.on_chain_start(serialized={"name": "x"}, inputs={}, run_id=run_id)
    handler.on_chain_error(error=ValueError("boom"), run_id=run_id)
    # 手动触发 finalize（on_chain_end 未调用时的兜底）
    handler._finalize(output=None, outputs_dict={})

    payload = mock_client.send.call_args.args[0]
    assert payload.status == "failed"
    assert payload.error["message"] == "boom"


def test_tool_events_collected():
    mock_client = MagicMock()
    handler = TraceCallbackHandler(client=mock_client)

    chain_id = uuid4()
    tool_id = uuid4()
    handler.on_chain_start(serialized={"name": "agent"}, inputs={}, run_id=chain_id)
    handler.on_tool_start(serialized={"name": "get_weather"}, input_str="广州", run_id=tool_id, parent_run_id=chain_id)
    handler.on_tool_end(output="晴天 25度", run_id=tool_id, parent_run_id=chain_id)
    handler.on_chain_end(outputs={}, run_id=chain_id)

    payload = mock_client.send.call_args.args[0]
    types = [e.event_type for e in payload.events]
    assert "tool_start" in types and "tool_end" in types


# ---------- Middleware 启发式识别 ----------

def test_detect_middleware_by_class_name():
    """PIIMiddleware 等内置中间件通过类名后缀识别。"""
    h = TraceCallbackHandler()
    is_mw, name, node, lc_source = h._detect_middleware(
        serialized={"id": ["langchain", "PIIMiddleware"]},
        name="PIIMiddleware",
        metadata={"langgraph_node": "PIIMiddleware"},
        tags=[],
    )
    assert is_mw is True
    assert name == "PIIMiddleware"
    assert node == "PIIMiddleware"
    assert lc_source == "pii"


def test_detect_middleware_by_tag():
    """自定义中间件可通过 tags 显式标注。"""
    h = TraceCallbackHandler()
    is_mw, name, _, lc_source = h._detect_middleware(
        serialized={"id": ["x", "y"]},
        name="y",
        metadata={},
        tags=["langchain:middleware:MyGuard"],
    )
    assert is_mw is True
    # 自定义 middleware 不在内置注册表中：保留候选名，lc_source 为 None
    assert name == "y"
    assert lc_source is None


def test_detect_middleware_node_name_uppercase():
    """兜底：node_name 首字母大写且非核心 node。"""
    h = TraceCallbackHandler()
    is_mw, name, node, lc_source = h._detect_middleware(
        serialized={},
        name=None,
        metadata={"langgraph_node": "MyCustomMiddleware"},
        tags=[],
    )
    assert is_mw is True
    assert node == "MyCustomMiddleware"
    assert name == "MyCustomMiddleware"
    # 非内置 middleware：lc_source 为 None
    assert lc_source is None


def test_not_middleware_for_agent_node():
    """agent 核心 node 不被误判。"""
    h = TraceCallbackHandler()
    is_mw, _, node, _ = h._detect_middleware(
        serialized={"id": ["langchain", "agent"]},
        name="agent",
        metadata={"langgraph_node": "agent"},
        tags=[],
    )
    assert is_mw is False
    assert node == "agent"


def test_not_middleware_for_tools_node():
    """tools 核心 node 不被误判。"""
    h = TraceCallbackHandler()
    is_mw, _, _, _ = h._detect_middleware(
        serialized={"id": ["langchain", "tools"]},
        name="tools",
        metadata={"langgraph_node": "tools"},
        tags=[],
    )
    assert is_mw is False


def test_middleware_event_marked_in_payload():
    """端到端：on_chain_start 注入 middleware 元数据。"""
    mock_client = MagicMock()
    handler = TraceCallbackHandler(client=mock_client, name="mw-test")
    rid = uuid4()
    handler.on_chain_start(
        serialized={"id": ["langchain", "PIIMiddleware"]},
        inputs={"input": "13800138000"},
        run_id=rid,
        metadata={"langgraph_node": "PIIMiddleware"},
    )
    handler.on_chain_end(outputs={"output": "***"}, run_id=rid)
    payload = mock_client.send.call_args.args[0]
    start_ev = payload.events[0]
    assert start_ev.is_middleware is True
    assert start_ev.middleware_name == "PIIMiddleware"
    assert start_ev.node_name == "PIIMiddleware"
    assert start_ev.lc_source == "pii"


def test_chain_end_inherits_middleware_metadata():
    """chain_end 事件应从缓存继承同 run 的 middleware 元数据。"""
    mock_client = MagicMock()
    handler = TraceCallbackHandler(client=mock_client, name="mw-inherit")
    rid = uuid4()
    handler.on_chain_start(
        serialized={"id": ["langchain", "PIIMiddleware[custom].before_model"]},
        inputs={},
        run_id=rid,
        metadata={"langgraph_node": "PIIMiddleware[custom].before_model"},
    )
    handler.on_chain_end(outputs={"messages": []}, run_id=rid)
    payload = mock_client.send.call_args.args[0]
    end_ev = next(e for e in payload.events if e.event_type == "chain_end")
    assert end_ev.is_middleware is True
    # 模糊匹配将 "PIIMiddleware[custom].before_model" 标准化为内置 "PIIMiddleware"
    assert end_ev.middleware_name == "PIIMiddleware"
    assert end_ev.lc_source == "pii"
