"""端到端测试：模拟 LangGraph 完整调用，含 PIIMiddleware + 模型 + SummarizationMiddleware。

结构：
  root (agent)
  └─ PIIMiddleware (chain_start/end)
  └─ chat_model (chat_model_start/end + llm_end)
  └─ SummarizationMiddleware (chain_start/end)
"""
import time
from uuid import uuid4

from agentlens_cb import TraceCallbackHandler

h = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="middleware-e2e-test",
)

# 1. 根 chain: agent
root = uuid4()
h.on_chain_start(
    {"id": ["langchain", "agent"]},
    {"messages": [{"role": "user", "content": "我的手机号是 13800138000"}]},
    run_id=root,
    metadata={"langgraph_node": "agent"},
)
time.sleep(0.02)

# 2. PIIMiddleware before_model
pii = uuid4()
h.on_chain_start(
    {"id": ["langchain", "PIIMiddleware"]},
    {"input": "我的手机号是 13800138000"},
    run_id=pii,
    parent_run_id=root,
    metadata={"langgraph_node": "PIIMiddleware"},
    tags=["langchain:middleware"],
)
time.sleep(0.05)
h.on_chain_end({"output": "我的手机号是 <PHONE_REDACTED>"}, run_id=pii)

# 3. chat_model
cm = uuid4()
h.on_chat_model_start(
    {"id": ["langchain", "ChatOpenAI"]},
    [[{"role": "user", "content": "我的手机号是 <PHONE_REDACTED>"}]],
    run_id=cm,
    parent_run_id=root,
    metadata={"langgraph_node": "model"},
)
time.sleep(0.1)
h.on_llm_end(
    {"generations": [[{"text": "好的，已收到。", "message": {"content": "好的，已收到。"}}]]},
    run_id=cm,
)

# 4. SummarizationMiddleware
sumr = uuid4()
h.on_chain_start(
    {"id": ["langchain", "SummarizationMiddleware"]},
    {"messages": []},
    run_id=sumr,
    parent_run_id=root,
    metadata={"langgraph_node": "SummarizationMiddleware"},
)
time.sleep(0.05)
h.on_chain_end({"messages": []}, run_id=sumr)

# 5. 根 chain 结束
h.on_chain_end(
    {"messages": [{"role": "assistant", "content": "好的，已收到。"}]},
    run_id=root,
)
print("middleware trace sent")
