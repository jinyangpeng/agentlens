# AI Agent 接入说明

> AgentLens 客户端回调（`agentlens-cb`）使用说明。

## 1. 安装 callback 包

在 AI Agent 项目中安装 `agentlens-cb`（≥0.6.0，新增 AgentLens 统一入口 + LoggerCallbackHandler + verbose 模式 + 13 个内置 middleware 适配 + 数据库持久化 + 统计模块）：

```bash
# 方式 A：从 PyPI 安装
pip install agentlens-cb

# 方式 B：从 wheel 安装（推荐，跨项目分发）
pip install agentlens_cb-0.6.0-py3-none-any.whl

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
> **升级提示**：升级到 0.6.0 前请先 `pip uninstall agentlens-cb langchain-trace-cb -y` 再装新版本。
>
> **依赖**：
> - `langchain-core>=0.3.0`
> - `httpx>=0.27.0`
> - Python ≥ 3.11
>
> 版本演进：
> - 0.1.0 → 0.2.0：加入 thread_id 提取
> - 0.2.0 → 0.3.0：修复守护线程被强杀问题（同步脚本也能正常推送）
> - 0.3.0 → 0.4.0：加入 middleware 启发式识别
> - 0.4.0 → 0.5.0：**重命名为 AgentLens**（pip 名 `agentlens-cb`、import 名 `agentlens_cb`），chain_end 事件继承 middleware 元数据
> - 0.5.0 → 0.6.0：**AgentLens 统一入口**（callback / 装饰器 / 上下文 / 手动推送）+ `LoggerCallbackHandler` + verbose 模式 + 13 个内置 middleware 适配 + 数据库持久化（SQLite / PostgreSQL）+ 统计模块

## 2. 使用方式

### 2.1 快速上手（TraceCallbackHandler）

最常用的接入方式，直接在 `agent.invoke` 时传入 callback：

```python
from agentlens_cb import TraceCallbackHandler

# 创建 handler，指向后端地址
trace_handler = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="my-agent",          # 可选：trace 名称
    tags=["prod"],            # 可选：标签
    metadata={"app": "xxx"},  # 可选：元数据
    verbose=True,             # 可选：终端实时打印调用链（v0.6.0+）
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

### 2.2 AgentLens 统一入口（v0.6.0+，推荐）

`AgentLens` 类整合了四种接入方式，所有方式共享同一个 `TraceClient`（连接复用 + 熔断降级），数据格式与后端 `POST /api/v1/traces` 对齐。

```python
from agentlens_cb import AgentLens

lens = AgentLens(
    endpoint="http://localhost:8000/api/v1/traces",
    verbose=True,                # 终端实时打印调用链
    timeout=2.0,                 # 推送超时秒数
    circuit_break_seconds=30.0,  # 熔断冷却
)

# 方式1：LangChain callback（最常用，等价于 TraceCallbackHandler）
result = agent.invoke(
    {...},
    config={"callbacks": [lens.trace_handler()]},
)

# 方式2：装饰器（不依赖 LangChain callback，自动追踪函数执行）
@lens.observe
def my_agent(query: str) -> str:
    return agent.invoke({"messages": [{"role": "user", "content": query}]})

# 带参数的装饰器
@lens.observe(name="custom", tags=["production"])
def another_agent(query: str) -> str:
    ...

# 方式3：上下文管理器（手动控制 trace 生命周期）
with lens.trace("my_agent") as ctx:
    ctx.event("chain_start", inputs={"query": "hello"})
    result = do_something()
    ctx.event("chain_end", outputs=result)
# 退出 with 块时自动推送 trace；异常退出时自动标记为 failed

# 方式4：手动推送（完全自主，适配任何 AI 框架）
lens.push(
    name="custom_agent",
    input={"query": "hello"},
    output={"answer": "hi"},
    events=[...],
)
```

**四种接入方式对比**：

| 方式 | 场景 | 依赖 LangChain callback | 控制粒度 |
|------|------|------------------------|----------|
| `trace_handler()` | LangChain/LangGraph 项目 | 是 | 全自动 |
| `@lens.observe` | 包装任意 Python 函数 | 否 | 函数级 |
| `with lens.trace(...)` | 手动控制 trace 边界 | 否 | 事件级 |
| `lens.push(...)` | 非 LangChain 框架 / 已有事件数据 | 否 | 完全自主 |

### 2.3 会话分组（thread_id）

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

> 使用 `AgentLens` 的上下文 / 装饰器 / 手动推送方式时，可显式传入 `thread_id`：
> ```python
> with lens.trace("my_agent", thread_id="session-001") as ctx: ...
> lens.push(name="custom", thread_id="session-001", input=..., output=...)
> ```

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

> v0.6.0+ 每个事件还携带 middleware 元数据：`is_middleware`、`middleware_name`、`node_name`、`lc_source`（详见 [§7 Middleware 追踪](#7-middleware-追踪v040)）。

## 4. 配置参数

### 4.1 TraceCallbackHandler

```python
from agentlens_cb import TraceCallbackHandler, TraceClient

TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",  # 后端地址
    name="my-agent",                                  # trace 名称
    tags=["prod"],                                    # 标签列表
    metadata={"key": "value"},                        # 元数据
    client=TraceClient(timeout=2.0),                  # 可选：自定义客户端
    verbose=False,                                    # v0.6.0+ 终端实时打印调用链
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `endpoint` | `str` | `http://localhost:8000/api/v1/traces` | 后端推送地址 |
| `name` | `str \| None` | `None` | trace 名称（未填则用根 chain 名） |
| `tags` | `list[str] \| None` | `None` | trace 标签 |
| `metadata` | `dict \| None` | `None` | trace 元数据 |
| `client` | `TraceClient \| None` | `None` | 自定义客户端（与 `endpoint` 二选一） |
| `verbose` | `bool` | `False` | v0.6.0+ 是否在终端实时打印调用链 |

### 4.2 AgentLens（v0.6.0+）

```python
from agentlens_cb import AgentLens

lens = AgentLens(
    endpoint="http://localhost:8000/api/v1/traces",
    verbose=False,
    timeout=2.0,
    headers=None,
    circuit_break_seconds=30.0,
)
```

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `endpoint` | `str` | `http://localhost:8000/api/v1/traces` | 后端推送地址 |
| `verbose` | `bool` | `False` | 是否在终端实时打印调用链 |
| `timeout` | `float` | `2.0` | HTTP 推送超时秒数 |
| `headers` | `dict[str, str] \| None` | `None` | 自定义 HTTP 头（如鉴权） |
| `circuit_break_seconds` | `float` | `30.0` | 熔断冷却秒数（`0` = 禁用熔断） |

`AgentLens.trace_handler()` 接受与 `TraceCallbackHandler` 相同的 `name` / `tags` / `metadata` / `verbose` 参数（`verbose` 默认继承 `AgentLens` 的设置）。

### 4.3 TraceClient

```python
from agentlens_cb import TraceClient

TraceClient(
    endpoint="http://localhost:8000/api/v1/traces",
    timeout=2.0,                # 超时秒数
    headers={"Authorization": "Bearer xxx"},  # 自定义请求头
    circuit_break_seconds=0,    # 0 = 禁用熔断
)
```

### 4.4 后端配置（环境变量）

后端通过环境变量配置（前缀 `TRACE_`，对应 `backend/.env`）：

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `TRACE_STORAGE_BACKEND` | `memory` | 存储后端：`memory` / `file` / `sqlite` / `postgresql` |
| `TRACE_FILE_STORAGE_DIR` | `./data/traces` | `file` 后端的存储目录 |
| `TRACE_DATABASE_URL` | （自动推导） | v0.6.0+ 数据库连接串，详见 [§8 存储扩展](#8-存储扩展) |
| `TRACE_CORS_ORIGINS` | `["http://localhost:5173"]` | CORS 允许的前端来源 |
| `TRACE_API_PREFIX` | `/api/v1` | API 路由前缀 |

## 5. 错误处理与降级

callback 推送失败**不会**抛异常影响 agent 执行，仅记录 warning 日志。降级机制：

- **异步后台发送**：trace 在后台线程推送，agent 主流程零阻塞
- **短超时**：2s 超时（可通过 `TraceClient(timeout=...)` 调整），后端不可达时不会长时间挂起
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
from agentlens_cb import AgentLens


def get_weather(city: str) -> str:
    """获取指定城市天气。"""
    return f"{city} 今天晴朗，25 度。"


model = ChatOpenAI(model="qwen-flash", base_url="...")
agent = create_react_agent(model=model, tools=[get_weather])

# v0.6.0+ 推荐：使用 AgentLens 统一入口
lens = AgentLens(
    endpoint="http://localhost:8000/api/v1/traces",
    verbose=True,  # 终端实时打印调用链
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "广州今天天气如何？"}]},
    config={
        "callbacks": [lens.trace_handler(name="weather-agent")],
        "configurable": {"thread_id": "session-001"},
    },
)

print(result["structured_response"])
```

执行后，在 http://localhost:5173 即可查看本次调用的完整轨迹。

### 装饰器方式（非 LangChain 项目也可用）

```python
from agentlens_cb import AgentLens

lens = AgentLens(endpoint="http://localhost:8000/api/v1/traces", verbose=True)

@lens.observe(name="qa-agent", tags=["production"])
def run_agent(query: str) -> str:
    # 任意业务逻辑，不限于 LangChain
    return f"answer to: {query}"

# 自动记录 trace，函数返回值作为 output；异常时自动标记为 failed
print(run_agent("hello"))
```

## 7. Middleware 追踪（v0.4.0+）

`create_agent(..., middleware=[...])` 中的中间件会被自动识别并在前端以橙色高亮显示。

### 7.1 识别策略（按优先级）

1. **显式 tag**：`tags` 含 `langchain:middleware` 前缀
2. **类名后缀**：类名以 `Middleware` 结尾（覆盖 PIIMiddleware、SummarizationMiddleware 等内置中间件）
3. **LangGraph node 兜底**：`metadata.langgraph_node` 存在且非 agent/tools/model 核心 node，且首字母大写

检测到 middleware 后，会通过 `middleware_registry.detect_middleware_type` 将类名标准化为内置 middleware 的标准类名，并填充 `lc_source`。未匹配到内置注册表的自定义 middleware 仍按原候选名返回，`lc_source=None`。

### 7.2 LangChain v1.3.11 内置 Middleware（13 个）

v0.6.0+ 内置 13 个 middleware 元数据注册表（`agentlens_cb.middleware_registry.BUILTIN_MIDDLEWARES`），前后端共享同一份配置，避免硬编码。

| 类名 | lc_source | 显示名 | 说明 |
|------|-----------|--------|------|
| `SummarizationMiddleware` | `summarization` | 摘要压缩 | 自动摘要历史消息 |
| `HumanInTheLoopMiddleware` | `human_in_the_loop` | 人工审批 | 暂停执行等待人工审批 |
| `ModelCallLimitMiddleware` | `model_call_limit` | 模型调用限制 | 限制模型调用次数 |
| `ToolCallLimitMiddleware` | `tool_call_limit` | 工具调用限制 | 限制工具调用次数 |
| `ModelFallbackMiddleware` | `model_fallback` | 模型回退 | 主模型失败时自动回退到备选模型 |
| `PIIMiddleware` | `pii` | PII 脱敏 | 检测和脱敏个人信息 |
| `TodoListMiddleware` | `todo_list` | 任务清单 | 任务规划和跟踪 |
| `LLMToolSelectorMiddleware` | `llm_tool_selector` | LLM 工具选择 | LLM 选择相关工具 |
| `ToolRetryMiddleware` | `tool_retry` | 工具重试 | 自动重试失败的工具调用 |
| `LLMToolEmulator` | `llm_tool_emulator` | LLM 工具模拟 | LLM 模拟工具执行结果 |
| `ContextEditingMiddleware` | `context_editing` | 上下文编辑 | 修剪或清理上下文 |
| `ShellToolMiddleware` | `shell_tool` | Shell 会话 | 持久 shell 会话 |
| `FilesystemFileSearchMiddleware` | `filesystem_file_search` | 文件搜索 | 文件系统搜索 |

每个 middleware 的完整元数据结构（`MiddlewareMeta`）：

| 字段 | 说明 | 示例 |
|------|------|------|
| `class_name` | 标准类名 | `SummarizationMiddleware` |
| `lc_source` | 标准化标识符（前后端通信） | `summarization` |
| `display_name` | UI 显示名 | `摘要压缩` |
| `icon` | lucide-react 图标名 | `FileText` |
| `color` | Tailwind 颜色名 | `purple` |
| `description` | 简短描述 | `自动摘要历史消息` |

### 7.3 前端可视化

| 视图 | 显示 |
|------|------|
| 调用树 | 橙色边框 + 齿轮图标 + middleware 显示名徽章 |
| 时间线 | 橙色节点 + Middleware 徽章 + 行为摘要 |
| 消息流 | 橙色横幅标记 middleware 边界 + start→end 行为描述 |
| Header | middleware 列表徽章（带触发次数，按 `lc_source` 着色） |

前端按 `lc_source` 查找对应颜色与图标（如 `pii` → `ShieldAlert` + `red`、`summarization` → `FileText` + `purple`），未命中内置注册表的 middleware 使用默认橙色 + 齿轮图标。

### 7.4 自定义中间件接入

**方式一：类名以 `Middleware` 结尾**（推荐，自动识别）

```python
from langchain.agents.middleware import AgentMiddleware
from langchain.agents import create_agent

class MyGuardMiddleware(AgentMiddleware):
    async def before_model(self, *args, **kwargs): ...

agent = create_agent(
    model=model,
    tools=[...],
    middleware=[MyGuardMiddleware()],
)
# 自动识别为 middleware，前端显示类名 "MyGuardMiddleware"
```

**方式二：手动添加 tag**（类名不以 `Middleware` 结尾时）

```python
from langchain.agents.middleware import AgentMiddleware

class MyGuard(AgentMiddleware):
    ...

agent = create_agent(model=model, tools=[...], middleware=[MyGuard()])

# 显式标注（可选，仅当前缀不匹配时需要）
agent.middleware[0].tags = ["langchain:middleware:MyGuard"]
```

**方式三：注册到内置表**（让自定义 middleware 也有标准 `lc_source`、颜色、图标）

在 `client/agentlens_cb/middleware_registry.py` 的 `BUILTIN_MIDDLEWARES` 中追加：

```python
"MyGuard": MiddlewareMeta(
    class_name="MyGuard",
    lc_source="my_guard",
    display_name="自定义守卫",
    icon="ShieldCheck",
    color="green",
    description="业务自定义守卫",
),
```

### 7.5 旧数据回填

后端可通过 `resolve_lc_source(lc_source, middleware_name)` 在缺少 `lc_source` 字段时通过 `middleware_name` 反查标准化标识符，便于历史 trace 在新前端中正确显示颜色和图标。

> **支持的 LangChain 版本**：>= 1.0（需要 `create_agent` API 和 LangGraph callback 元数据）
>
> **验证脚本**：`backend/tests/manual_middleware_test.py` 模拟含 PIIMiddleware + 模型 + SummarizationMiddleware 的完整调用，可直接运行验证。

## 8. 存储扩展

后端默认使用内存存储（重启丢失）。v0.6.0+ 内置四种存储后端，通过环境变量 `TRACE_STORAGE_BACKEND` 切换：

| 后端 | 配置项 | 适用场景 |
|------|--------|----------|
| `memory`（默认） | 无 | 本地开发、调试 |
| `file` | `TRACE_FILE_STORAGE_DIR` | 单机持久化、轻量部署 |
| `sqlite` | `TRACE_DATABASE_URL` | 单机持久化、并发查询 |
| `postgresql` | `TRACE_DATABASE_URL`（必填） | 生产环境、多实例共享 |

### 8.1 SQLite（推荐用于单机持久化）

```bash
# backend/.env
TRACE_STORAGE_BACKEND=sqlite
# 留空时自动推导为 sqlite+aiosqlite:///./data/traces.db
TRACE_DATABASE_URL=sqlite+aiosqlite:///./data/traces.db
```

启动时自动建表（`Base.metadata.create_all`，幂等），无需手动迁移。SQLite 文件父目录会自动创建。

### 8.2 PostgreSQL（推荐用于生产）

```bash
# backend/.env
TRACE_STORAGE_BACKEND=postgresql
TRACE_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/agentlens
```

> **依赖**：PostgreSQL 后端需要 `asyncpg` 驱动，安装方式：
> ```bash
> pip install -e "./backend[postgres]"
> # 或
> pip install asyncpg
> ```
>
> **强制配置**：`storage_backend=postgresql` 时**必须**显式配置 `TRACE_DATABASE_URL`，否则启动会抛 `ValueError`。

### 8.3 迁移说明

- **内存 → 数据库**：直接切换 `TRACE_STORAGE_BACKEND` 即可，历史内存数据不迁移（重启即丢）
- **SQLite → PostgreSQL**：建议用 `pgloader` 或手动导出导入：
  ```bash
  # 导出
  sqlite3 ./data/traces.db ".dump traces events" > dump.sql
  # 转换语法后导入 PostgreSQL（注意 JSON 列、自增主键差异）
  psql -d agentlens -f dump.sql
  ```
- **表结构变更**：当前采用 `create_all` 自动建表（不做 schema 迁移）。如需修改字段，需要手动 `DROP TABLE` 重建或使用 Alembic。

### 8.4 自定义存储后端

如需扩展其他存储（如 MongoDB、Redis），继承 `app.repositories.base.TraceRepository` 并在 `app/dependencies.py:get_repository()` 中注册：

```python
# app/repositories/mongo.py
from app.repositories.base import TraceRepository

class MongoRepository(TraceRepository):
    async def create(self, trace_create): ...
    async def get(self, trace_id): ...
    async def list(self, *, limit, offset, thread_id): ...
    async def list_by_thread(self, thread_id): ...
    async def count(self): ...
    async def delete(self, trace_id): ...

# app/dependencies.py
@lru_cache
def get_repository() -> TraceRepository:
    backend = settings.storage_backend
    if backend == "mongo":
        return MongoRepository(settings.mongo_url)
    # ... 其他分支
```

## 9. verbose 模式（终端日志，v0.6.0+）

verbose 模式在 LangChain 调用过程中实时打印结构化日志到终端，包括 chain/llm/tool 的开始、结束、耗时、token 用量等。通过标准 `logging` 模块输出，可被日志体系接管。

### 9.1 三种启用方式

**方式一：`TraceCallbackHandler(verbose=True)`**（推送 trace + 终端打印）

```python
from agentlens_cb import TraceCallbackHandler

handler = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    verbose=True,  # 推送 trace 的同时实时打印调用链
)
result = agent.invoke({...}, config={"callbacks": [handler]})
```

**方式二：`AgentLens(verbose=True)`**（推荐）

```python
from agentlens_cb import AgentLens

lens = AgentLens(
    endpoint="http://localhost:8000/api/v1/traces",
    verbose=True,
)
# trace_handler() 自动继承 verbose 设置
result = agent.invoke({...}, config={"callbacks": [lens.trace_handler()]})
```

**方式三：`LoggerCallbackHandler`（仅终端打印，不推送 trace）**

适合本地调试、CI 日志、不想搭后端的场景：

```python
from agentlens_cb import LoggerCallbackHandler

handler = LoggerCallbackHandler()  # 默认 INFO 级别
result = agent.invoke({...}, config={"callbacks": [handler]})
```

也可与 `TraceCallbackHandler` 同时使用（两个 handler 互不影响）：

```python
from agentlens_cb import TraceCallbackHandler, LoggerCallbackHandler

result = agent.invoke(
    {...},
    config={"callbacks": [
        TraceCallbackHandler(endpoint="..."),  # 推送 trace
        LoggerCallbackHandler(),                # 仅终端打印
    ]},
)
```

### 9.2 输出示例

```
2026-07-07 10:23:01 | INFO  | [CHAIN START] create_react_agent (depth=0)
  input:
{"messages": [{"role": "user", "content": "广州今天天气如何？"}]}
  [LLM START] ChatOpenAI
  [LLM START]   messages:
[{"role": "user", "content": "广州今天天气如何？"}]
  [LLM END]   (0.842s)
  [LLM END]   tool_calls: get_weather({"city": "广州"})
  [LLM END]   tokens: prompt=42, completion=18, total=60
  [LLM END]   cumulative: prompt=42, completion=18, total=60
  [TOOL START] get_weather: 广州
  [TOOL END]   (0.003s) 广州 今天晴朗，25 度。
[CHAIN END]   (1.205s)
[SUMMARY] total tokens: prompt=42, completion=18, total=60
```

特性：
- 自动按 `parent_run_id` 链推算嵌套深度并缩进
- LLM 调用打印耗时、tool_calls、token 用量（含累计统计）
- Chain / Tool 调用打印耗时和输入输出预览（默认截断 500 字符）
- 根 chain 结束时打印 token 汇总

### 9.3 日志级别与配置

```python
import logging

# 修改 LoggerCallbackHandler 输出级别
from agentlens_cb import LoggerCallbackHandler
handler = LoggerCallbackHandler(level=logging.DEBUG)

# 修改日志格式（影响 logger 名 "agentlens.verbose"）
logging.getLogger("agentlens.verbose").setLevel(logging.DEBUG)
```

## 10. 统计模块（v0.6.0+）

统计模块提供三个维度的聚合分析，便于排查高频问题、监控 token 消耗、定位慢调用。

### 10.1 统计维度

| 维度 | 端点 | 说明 |
|------|------|------|
| 会话（session） | `GET /api/v1/stats/tokens?dimension=session` | 按 `thread_id` 聚合：prompt/completion/total tokens、调用次数 |
| 用户（user） | `GET /api/v1/stats/tokens?dimension=user` | 按 `metadata.user_id` 聚合（需在推送 trace 时写入 `metadata={"user_id": "..."}`） |
| 应用（app） | `GET /api/v1/stats/tokens?dimension=app` | 按 `trace.name` 聚合：prompt/completion/total tokens、调用次数 |
| 总体概览 | `GET /api/v1/stats/overview` | trace 总数、token 总量、会话数、平均 token/trace、成功率 |

### 10.2 查询参数

所有统计端点支持以下查询参数：

| 参数 | 类型 | 说明 |
|------|------|------|
| `start_time` | `str` (ISO 8601) | 起始时间（含），如 `2026-07-01T00:00:00Z` |
| `end_time` | `str` (ISO 8601) | 结束时间（不含） |
| `limit` | `int` | 返回条数，默认 50，最大 500 |
| `status` | `str` | 按状态过滤：`succeeded` / `failed` |

### 10.3 响应示例

`GET /api/v1/stats/tokens?dimension=session`：

```json
{
  "dimension": "thread",
  "items": [
    {
      "key": "user-123-session-1",
      "trace_count": 12,
      "success_count": 11,
      "failed_count": 1,
      "total_duration_ms": 18420,
      "avg_duration_ms": 1535,
      "p50_duration_ms": 1200,
      "p95_duration_ms": 3200,
      "last_seen": "2026-07-07T10:23:01Z"
    }
  ],
  "total": 1
}
```

### 10.4 前端统计页面

前端（`http://localhost:5173`）新增「统计」入口（侧边栏 Sidebar），提供：

- **会话榜**：trace 数 Top N 的会话，附成功率、平均耗时
- **用户榜**：调用量 Top N 的用户，附失败率红色高亮
- **应用榜**：各 agent name 的调用量、P50/P95 耗时柱状图
- **时间筛选**：近 1 小时 / 24 小时 / 7 天 / 自定义区间

> 统计端点依赖数据库后端（`sqlite` / `postgresql`）才能高效聚合；`memory` / `file` 后端也支持但数据量大时性能较差。

### 10.5 客户端配合

为了让「用户维度」生效，推送 trace 时需要把 `user_id` 写入 `metadata`：

```python
from agentlens_cb import AgentLens

lens = AgentLens(endpoint="http://localhost:8000/api/v1/traces")

# 方式1：trace_handler
result = agent.invoke(
    {...},
    config={"callbacks": [lens.trace_handler(
        metadata={"user_id": "u-1001", "app": "support-bot"},
    )]},
)

# 方式2：手动推送
lens.push(
    name="qa-agent",
    input={...},
    output={...},
    metadata={"user_id": "u-1001", "app": "support-bot"},
)
```

## 11. API 速查

后端 REST API（前缀 `/api/v1`）：

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/traces` | 上报一个完整 trace |
| `GET` | `/traces` | 分页列出 trace（支持 `thread_id` 过滤） |
| `GET` | `/traces/by_thread/{thread_id}` | 按会话列出全部 trace |
| `GET` | `/traces/count/total` | trace 总数 |
| `GET` | `/traces/{trace_id}` | 获取单个 trace 详情（含事件） |
| `DELETE` | `/traces/{trace_id}` | 删除 trace |
| `GET` | `/stats/tokens?dimension=session\|user\|app` | v0.6.0+ token 消耗统计（支持三个维度） |
| `GET` | `/stats/overview` | v0.6.0+ 总体概览指标 |

## 12. 模块导出

`agentlens_cb` 顶层导出：

```python
from agentlens_cb import (
    TraceCallbackHandler,   # LangChain BaseCallbackHandler 实现
    TraceClient,            # HTTP 客户端（异步、可降级）
    LoggerCallbackHandler,  # v0.6.0+ 仅终端打印日志的 callback
    AgentLens,              # v0.6.0+ 统一入口（callback + 装饰器 + 上下文 + 手动推送）
    TraceContext,           # v0.6.0+ AgentLens.trace() 返回的上下文对象
    EventPayload,           # 事件载荷模型
    TracePayload,           # trace 载荷模型
)

# 内置 middleware 注册表（高级用法）
from agentlens_cb.middleware_registry import (
    BUILTIN_MIDDLEWARES,    # dict[str, MiddlewareMeta]
    LC_SOURCE_MAP,          # dict[str, MiddlewareMeta]
    detect_middleware_type, # (name) -> MiddlewareMeta | None
    resolve_lc_source,      # (lc_source, middleware_name) -> str | None
)
```
