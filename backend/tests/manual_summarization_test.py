"""验证 SummarizationMiddleware 效果：模拟真实场景，inputs 含长历史，outputs 应该更短。"""
import time
from uuid import uuid4

from agentlens_cb import TraceCallbackHandler

h = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="summarization-effect-test",
)

# 根 chain
root = uuid4()
h.on_chain_start(
    {"id": ["langchain", "agent"]},
    {"input": "user input"},
    run_id=root,
    metadata={"langgraph_node": "agent"},
)
time.sleep(0.02)

# 模拟 SummarizationMiddleware: 输入是 10 条历史消息，输出是 1 条 summary
sumr = uuid4()
long_history = [
    {"role": "user", "content": f"问题{i}：请帮我详细解释 LangChain 的 Memory 机制和实现原理"}
    for i in range(10)
]
h.on_chain_start(
    {"id": ["langchain", "SummarizationMiddleware"]},
    {"messages": long_history},
    run_id=sumr,
    parent_run_id=root,
    metadata={"langgraph_node": "SummarizationMiddleware"},
)
time.sleep(0.05)
# 输出：1 条 summary 消息（被压缩的）
summary_messages = [
    {"role": "system", "content": "[Summary] 用户询问了 10 个关于 LangChain Memory 的问题"}
]
h.on_chain_end({"messages": summary_messages}, run_id=sumr)

# 根 chain 结束
h.on_chain_end(
    {"messages": summary_messages + [{"role": "assistant", "content": "已处理。"}]},
    run_id=root,
)
print("summarization effect trace sent")
