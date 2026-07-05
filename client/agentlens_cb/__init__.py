"""AgentLens Callback 包。

用法:
    from agentlens_cb import TraceCallbackHandler

    handler = TraceCallbackHandler(endpoint="http://localhost:8000/api/v1/traces")
    result = agent.invoke({...}, config={"callbacks": [handler]})
"""
from agentlens_cb.callback import TraceCallbackHandler
from agentlens_cb.client import TraceClient

__all__ = ["TraceCallbackHandler", "TraceClient"]
