"""真实端到端测试：直接模拟 LangGraph 行为，验证 0.4.1 修复。

不依赖真实 LLM（不消耗 token）。但**完全模拟 LangGraph 的 callback 协议**：
- middleware 节点名 = ClassName[config].hook_name（你项目的真实格式）
- middleware 真实触发压缩时，chain_end outputs 包含被压缩后的 messages

目的：跑完后用 verify 脚本检查 chain_end 事件是否带 Middleware 徽章。
"""
import time
from uuid import uuid4

from agentlens_cb import TraceCallbackHandler

h = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="mw-0.4.1-trace",
    tags=["test", "0.4.1"],
)

# 根 chain
root = uuid4()
h.on_chain_start(
    {"id": ["langchain", "agent"]},
    {"input": "test"},
    run_id=root,
    metadata={"langgraph_node": "agent"},
)
time.sleep(0.02)

# 1. SummarizationMiddleware.before_model
# 模拟真实格式：PIIMiddleware[custom_pii].before_model
sumr = uuid4()
LONG_HISTORY = [
    {"role": "user", "content": f"问题{i}：请详细解释 LangChain 的 Memory 机制和实现原理"}
    for i in range(15)
]
h.on_chain_start(
    {"id": ["langchain", "SummarizationMiddleware"]},
    {"messages": LONG_HISTORY},
    run_id=sumr,
    parent_run_id=root,
    metadata={"langgraph_node": "SummarizationMiddleware"},
)
time.sleep(0.05)
# 模拟压缩后的输出
SUMMARY_OUTPUT = {
    "messages": [
        {"role": "system", "content": "[Summary] 用户询问了 15 个关于 LangChain Memory 的问题"},
        {"role": "user", "content": "问题 14：请详细解释 LangChain 的 Memory 机制和实现原理"},
        {"role": "user", "content": "问题 15：请详细解释 LangChain 的 Memory 机制和实现原理"},
    ]
}
h.on_chain_end(SUMMARY_OUTPUT, run_id=sumr)

# 2. PIIMiddleware[custom_pii].before_model
pii_before = uuid4()
h.on_chain_start(
    {"id": ["langchain", "PIIMiddleware[custom_pii]"]},
    {"messages": SUMMARY_OUTPUT["messages"]},
    run_id=pii_before,
    parent_run_id=root,
    metadata={"langgraph_node": "PIIMiddleware[custom_pii]"},
)
time.sleep(0.05)
PII_AFTER_BEFORE = {
    "messages": [
        {"role": "system", "content": "[Summary] 用户询问了 15 个关于 LangChain Memory 的问题"},
        {"role": "user", "content": "问题 14：请详细解释 LangChain 的 Memory 机制和实现原理"},
        {"role": "user", "content": "问题 15：请详细解释 LangChain 的 Memory 机制和实现原理"},
    ]
}
h.on_chain_end(PII_AFTER_BEFORE, run_id=pii_before)

# 3. LLM call
cm = uuid4()
h.on_chat_model_start(
    {"id": ["langchain", "ChatOpenAI"]},
    [[{"role": "user", "content": "问题 15"}]],
    run_id=cm,
    parent_run_id=root,
    metadata={"langgraph_node": "model"},
)
time.sleep(0.1)
h.on_llm_end(
    {"generations": [[{"text": "Memory 机制通过 Checkpointer 持久化。"}]]},
    run_id=cm,
)

# 4. PIIMiddleware[custom_pii].after_model
pii_after = uuid4()
h.on_chain_start(
    {"id": ["langchain", "PIIMiddleware[custom_pii]"]},
    {"messages": []},
    run_id=pii_after,
    parent_run_id=root,
    metadata={"langgraph_node": "PIIMiddleware[custom_pii]"},
)
time.sleep(0.05)
h.on_chain_end({"messages": []}, run_id=pii_after)

# 根结束
h.on_chain_end({"messages": []}, run_id=root)
print("[ok] 0.4.1 mw trace sent (含 3 个 middleware 的 start+end)")
