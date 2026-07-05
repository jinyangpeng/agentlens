# AI Agent 接入说明

> AgentLens 客户端回调（`agentlens-cb`）使用说明。

## 1. 安装 callback 包

在 AI Agent 项目中安装 `agentlens-cb`（≥0.5.0，支持 middleware 识别 + thread_id + 降级 + session 退出等待）：

```bash
# 方式 A：从 PyPI 安装
pip install agentlens-cb

# 方式 B：从 wheel 安装（推荐，跨项目分发）
pip install agentlens_cb-0.5.0-py3-none-any.whl

# 方式 C：从源码安装（开发模式）
pip install -e ./client

# 方式 D：从 git 安装
pip install git+https://your-repo.git@main#subdirectory=client
```

> **命名规则**：
> - pip 包名：`agentlens-cb`（PEP 508，**连字符 `-`**）
> - Python import 路径：`agentlens_cb`（PEP 8，**下划线 `_`**）
> - 两者指向同一个包。
>
> **升级提示**：升级到 0.5.0 前请先 `pip uninstall agentlens-cb langchain-trace-cb -y` 再装新版本。
>
> 版本演进：
> - 0.1.0 → 0.2.0：加入 thread_id 提取
> - 0.2.0 → 0.3.0：修复守护线程被强杀问题（同步脚本也能正常推送）
> - 0.3.0 → 0.4.0：加入 middleware 启发式识别
> - 0.4.0 → 0.5.0：**重命名为 AgentLens**（pip 名 `agentlens-cb`、import 名 `agentlens_cb`），chain_end 事件继承 middleware 元数据

## 2. 使用方式

```python
from agentlens_cb import TraceCallbackHandler

# 创建 handler，指向后端地址
trace_handler = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="my-agent",          # 可选：trace 名称
    tags=["prod"],            # 可选：标签
    metadata={"app": "xxx"},  # 可选：元数据
)

# 在 invoke 时传入
result = agent.invoke(
    {"messages": [{"role": "user", "content": "广州今天天气如何？"}]},
    config={
        "callbacks": [trace_handler],
        # 传入 thread_id 后，同会话的多次调用会在前端分组显示
        "configurable": {"thread_id": "user-123-session-1"},
    },
)
```

callback 会在 invoke 执行期间采集所有事件（LLM/Chain/Tool/Agent 等），在根 chain 结束时一次性 POST 到后端。

### 会话分组（thread_id）

LangGraph / LangChain 会把 `config["configurable"]["thread_id"]` 自动注入到每个回调事件的 metadata 里，callback 会自动提取并随 trace 推送。前端列表页会按 thread_id 分组显示，详情页 Header 显示会话徽章（点击可筛选）。

提取逻辑（按优先级）：
1. `metadata.configurable.thread_id`（LangGraph 标准）
2. `metadata.thread_id`（兜底）
3. `metadata.configurable.checkpoint_id`（部分 LangGraph 版本）

如未提取到，可开启调试日志确认：
```python
import logging
logging.getLogger("agentlens_cb").setLevel(logging.DEBUG)
```

## 3. 采集的事件类型

| 事件 | 说明 |
|------|------|
| llm_start / chat_model_start | LLM / Chat 模型开始 |
| llm_end | LLM 结束（含 token 用量） |
| llm_error | LLM 错误 |
| chain_start / chain_end | Chain 开始/结束 |
| chain_error | Chain 错误 |
| tool_start / tool_end | 工具开始/结束 |
| tool_error | 工具错误 |
| agent_action / agent_finish | Agent 动作/结束 |
| retriever_start / retriever_end | 检索器开始/结束 |
| text | 任意文本 |

每个事件包含 `run_id` / `parent_run_id`，用于构建调用树。

## 4. 配置参数

```python
from agentlens_cb import TraceCallbackHandler, TraceClient

TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",  # 后端地址
    name="my-agent",                                  # trace 名称
    tags=["prod"],                                    # 标签列表
    metadata={"key": "value"},                        # 元数据
    client=TraceClient(timeout=5.0),                  # 可选：自定义客户端
)
```

## 5. 错误处理与降级

callback 推送失败**不会**抛异常影响 agent 执行，仅记录 warning 日志。降级机制：

- **异步后台发送**：trace 在守护线程推送，agent 主流程零阻塞
- **短超时**：2s 超时，后端不可达时不会长时间挂起
- **熔断冷却**：首次失败后 30s 内跳过发送，避免每条 trace 都等超时
- **进程退出**：非守护线程 + `atexit` 等待最多 3s，确保同步脚本也能推送成功

如需自定义超时或禁用熔断：
```python
from agentlens_cb import TraceClient

TraceClient(
    endpoint="http://localhost:8000/api/v1/traces",
    timeout=5.0,                # 超时秒数
    circuit_break_seconds=0,    # 0 = 禁用熔断
)
```

## 6. 完整示例（基于 create_react_agent）

```python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from agentlens_cb import TraceCallbackHandler


def get_weather(city: str) -> str:
    """获取指定城市天气。"""
    return f"{city} 今天晴朗，25 度。"


model = ChatOpenAI(model="qwen-flash", base_url="...")
agent = create_react_agent(model=model, tools=[get_weather])

handler = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="weather-agent",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "广州今天天气如何？"}]},
    config={
        "callbacks": [handler],
        "configurable": {"thread_id": "session-001"},
    },
)

print(result["structured_response"])
```

执行后，在 http://localhost:5173 即可查看本次调用的完整轨迹。

## 7. Middleware 追踪（v0.4.0+）

`create_agent(..., middleware=[...])` 中的中间件会被自动识别并在前端以橙色高亮显示。

### 识别策略（按优先级）

1. **显式 tag**：`tags` 含 `langchain:middleware` 前缀
2. **类名后缀**：类名以 `Middleware` 结尾（覆盖 PIIMiddleware、SummarizationMiddleware 等内置中间件）
3. **LangGraph node 兜底**：`metadata.langgraph_node` 存在且非 agent/tools/model 核心 node

### 前端可视化

| 视图 | 显示 |
|------|------|
| 调用树 | 橙色边框 + 齿轮图标 + middleware 类名徽章 |
| 时间线 | 橙色节点 + Middleware 徽章 + 行为摘要 |
| 消息流 | 橙色横幅标记 middleware 边界 + start→end 行为描述 |
| Header | middleware 列表徽章（带触发次数） |

### 自定义中间件显式标注

如果你的自定义 middleware 类名不以 `Middleware` 结尾，可以在实例化后手动添加 tag：

```python
from langchain.agents.middleware import AgentMiddleware
from langchain.agents import create_agent

class MyGuard(AgentMiddleware):
    ...

agent = create_agent(
    model=model,
    tools=[...],
    middleware=[MyGuard()],
)

# 显式标注（可选，仅当前缀不匹配时需要）
agent.middleware[0].tags = ["langchain:middleware:MyGuard"]
```

> **支持的 LangChain 版本**：>= 1.0（需要 `create_agent` API 和 LangGraph callback 元数据）
>
> **验证脚本**：`backend/tests/manual_middleware_test.py` 模拟含 PIIMiddleware + 模型 + SummarizationMiddleware 的完整调用，可直接运行验证。

## 8. 存储扩展

后端默认使用内存存储（重启丢失）。如需持久化：

```bash
# backend/.env
TRACE_STORAGE_BACKEND=file
TRACE_FILE_STORAGE_DIR=./data/traces
```

如需扩展数据库存储，继承 `app.repositories.base.TraceRepository` 并在 `dependencies.py` 中注册。
