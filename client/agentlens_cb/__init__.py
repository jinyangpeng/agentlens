"""AgentLens Callback 包。

用法:
    # 方式1：LangChain callback（最常用）
    from agentlens_cb import TraceCallbackHandler
    handler = TraceCallbackHandler(endpoint="http://localhost:8000/api/v1/traces", verbose=True)
    result = agent.invoke({...}, config={"callbacks": [handler]})

    # 方式2：AgentLens 统一入口（支持 callback + 装饰器 + 上下文 + 手动推送）
    from agentlens_cb import AgentLens
    lens = AgentLens(endpoint="http://localhost:8000/api/v1/traces", verbose=True)

    # callback
    result = agent.invoke({...}, config={"callbacks": [lens.trace_handler()]})

    # 装饰器
    @lens.observe
    def my_agent(query): ...

    # 上下文
    with lens.trace("my_agent") as ctx: ...

    # 手动推送
    lens.push(name="custom", input={...}, output={...})

    # 独立终端日志（不推送 trace）
    from agentlens_cb import LoggerCallbackHandler
    handler = LoggerCallbackHandler()
"""
from agentlens_cb.callback import TraceCallbackHandler
from agentlens_cb.client import TraceClient
from agentlens_cb.lens import AgentLens, TraceContext
from agentlens_cb.logger_handler import LoggerCallbackHandler
from agentlens_cb.models import EventPayload, TracePayload

__all__ = [
    "TraceCallbackHandler",
    "TraceClient",
    "LoggerCallbackHandler",
    "AgentLens",
    "TraceContext",
    "EventPayload",
    "TracePayload",
]
