# Middleware 全链路追踪实施计划

> **For agentic workers:** 按 Task 顺序执行；每完成一个 Task 跑对应测试。

**Goal:** 让前端能识别 LangChain v1.3.11 的 `AgentMiddleware`（内置 + 自定义），在调用树/时间线/消息流中专门区分显示，便于追踪 PII / Summarization / 自定义 middleware 的执行边界。

**Architecture:**
- 不改 LangChain 协议，纯前端读取 callback 透传的 `metadata.langgraph_node` / `langgraph_path` 字段识别 middleware
- client 在 trace 事件元数据中增加 `is_middleware: bool` 与 `middleware_name: str | None`，便于前端无需启发式判断
- 后端 Pydantic 模型补 `is_middleware` / `middleware_name` / `node_name` 字段，向后兼容
- 前端 CallTree / 时间线 / 消息流三处增加 middleware 视觉识别 + 边界标注

**Tech Stack:** Pydantic v2、FastAPI、React 18、TypeScript、TailwindCSS

**前置知识:**
- LangChain v1.3.11 的 `create_agent(middleware=[...])` 把每个 middleware hook 编译为 LangGraph node
- LangGraph callback 在每个 event 的 `metadata` 注入 `langgraph_node`（如 `"agent"`、`"tools"`、`"_write"`）和 `langgraph_path`（如 `("__pregel_pull", "agent")`）
- 内置 middleware 类名后缀为 `Middleware`（如 `PIIMiddleware`、`SummarizationMiddleware`）
- 自定义 middleware 继承 `AgentMiddleware`，类名可由用户决定——我们用以下启发式识别：
  1. `metadata.langgraph_node` 存在且不等于 `"agent"` / `"tools"` / `"model"`（agent 核心 node）
  2. `name` 字段以 `Middleware` 结尾，或 `serialized.id` 末段以 `Middleware` 结尾
  3. `tags` 包含 `"langchain:middleware"`

---

## File Structure

**后端改动:**
- 修改 `backend/app/models/event.py` — 加 `is_middleware` / `middleware_name` / `node_name` 字段（默认 None/False）
- 不动 storage：旧 trace 无此字段，自动 None，新 trace 自动填充

**client 改动:**
- 修改 `client/langchain_trace_cb/models.py` — `EventPayload` 加同样字段
- 修改 `client/langchain_trace_cb/callback.py` — 新增 `_detect_middleware()` 启发式方法，在 `on_chain_start` / `on_chat_model_start` / `on_tool_start` / `on_llm_start` 注入
- 修改 `client/langchain_trace_cb/__init__.py` — 导出新版本号

**前端改动:**
- 修改 `frontend/src/types/trace.ts` — `TraceEvent` 加 `is_middleware?` / `middleware_name?` / `node_name?`
- 修改 `frontend/src/components/CallTree.tsx` — middleware 节点特殊图标/颜色；子节点折叠逻辑保留
- 修改 `frontend/src/components/EventTimeline.tsx` — middleware 事件用专门色调 + 节点名标签
- 修改 `frontend/src/components/MessageFlow.tsx` — middleware 边界横幅
- 修改 `frontend/src/components/TraceDetailHeader.tsx` — middleware 列表徽章（统计 trace 内 middleware 出现次数）

**测试改动:**
- 修改 `client/tests/test_callback.py` — 加 `test_detect_middleware_*` 用例
- 修改 `backend/tests/test_event_schema.py`（如无则新建）— 验证后端模型接受新字段

**文档改动:**
- 修改 `docs/AI-Agent接入说明.md` — 加 "Middleware 追踪" 章节
- 修改 `docs/开发环境启动.md` — 加 "测试 middleware 追踪" 段落

---

## Task 1: 后端 Event 模型扩展

**Files:**
- Modify: `backend/app/models/event.py`

- [ ] **Step 1: 修改 `Event` 模型加 3 字段**

在 `Event` 类（第 29 行起）增加：
```python
is_middleware: bool = False  # 是否为 middleware 触发的回调
middleware_name: str | None = None  # middleware 类名（如 "PIIMiddleware"）
node_name: str | None = None  # LangGraph node 名（来自 metadata.langgraph_node）
```

- [ ] **Step 2: 跑测试验证向后兼容**

Run: `cd backend && python -m pytest tests/ -q`
Expected: 全绿（默认 False/None 不会破坏旧数据）

- [ ] **Step 3: 重启后端**（无 reload）

`python run.py` 已在前台运行，kill 后重启即可。

---

## Task 2: client 事件模型扩展

**Files:**
- Modify: `client/langchain_trace_cb/models.py`

- [ ] **Step 1: `EventPayload` 加 3 字段**

第 13 行起 `EventPayload` 类末尾加：
```python
is_middleware: bool = False
middleware_name: str | None = None
node_name: str | None = None
```

- [ ] **Step 2: 跑现有测试**

Run: `cd client && python -m pytest tests/ -q`
Expected: 3/3 通过

---

## Task 3: client callback 启发式识别 middleware

**Files:**
- Modify: `client/langchain_trace_cb/callback.py`

- [ ] **Step 1: 新增 `_detect_middleware()` 静态方法**

在 `_extract_thread_id` 后（约 109 行）新增：
```python
@staticmethod
def _detect_middleware(
    serialized: dict | None,
    name: str | None,
    metadata: dict | None,
    tags: list[str] | None,
) -> tuple[bool, str | None, str | None]:
    """启发式判断 callback event 是否由 middleware 触发。

    Returns: (is_middleware, middleware_name, node_name)
    """
    node_name = None
    if isinstance(metadata, dict):
        node_name = metadata.get("langgraph_node")
        if isinstance(node_name, str) and node_name:
            pass
        else:
            node_name = None

    # 提取类名候选：serialized.id 末段 > name > node_name
    class_candidate: str | None = None
    if isinstance(serialized, dict):
        sid = serialized.get("id")
        if isinstance(sid, list) and sid:
            last = sid[-1]
            if isinstance(last, str) and last:
                class_candidate = last
    if not class_candidate and isinstance(name, str) and name:
        class_candidate = name
    if not class_candidate and node_name:
        class_candidate = node_name

    tags_list = tags or []

    # 启发式 1: 显式 langchain:middleware tag
    if any(isinstance(t, str) and t.startswith("langchain:middleware") for t in tags_list):
        return True, class_candidate, node_name

    # 启发式 2: 类名以 Middleware 结尾
    if class_candidate and class_candidate.endswith("Middleware"):
        return True, class_candidate, node_name

    # 启发式 3: node_name 存在且非 agent/tools/model（说明是中间节点）
    if node_name and node_name not in {"agent", "tools", "model"}:
        # 进一步：node_name 像类名（首字母大写）
        if node_name[0].isupper() and node_name not in {"_write", "__start__", "__end__"}:
            return True, class_candidate, node_name

    return False, None, node_name
```

- [ ] **Step 2: 在 `on_chain_start` / `on_chat_model_start` / `on_tool_start` / `on_llm_start` 注入**

修改 `on_chain_start`（约 157 行），在 `_add` 前加：
```python
is_mw, mw_name, node = self._detect_middleware(serialized, name, metadata, tags)
```
并把 `is_middleware=is_mw, middleware_name=mw_name, node_name=node` 加到 `EventPayload(...)` 参数里。

对 `on_chat_model_start`（约 123 行）、`on_tool_start`（约 192 行）、`on_llm_start`（约 111 行）做同样处理。

- [ ] **Step 3: 写测试**

新建/修改 `client/tests/test_callback.py`，加：
```python
def test_detect_middleware_by_class_name():
    from langchain_trace_cb.callback import TraceCallbackHandler
    h = TraceCallbackHandler()
    is_mw, name, node = h._detect_middleware(
        serialized={"id": ["langchain", "PIIMiddleware"]},
        name="PIIMiddleware",
        metadata={"langgraph_node": "PIIMiddleware"},
        tags=[],
    )
    assert is_mw is True
    assert name == "PIIMiddleware"
    assert node == "PIIMiddleware"


def test_detect_middleware_by_tag():
    from langchain_trace_cb.callback import TraceCallbackHandler
    h = TraceCallbackHandler()
    is_mw, _, _ = h._detect_middleware(
        serialized={"id": ["x", "y"]},
        name="y",
        metadata={},
        tags=["langchain:middleware:MyGuard"],
    )
    assert is_mw is True


def test_detect_middleware_node_name_uppercase():
    from langchain_trace_cb.callback import TraceCallbackHandler
    h = TraceCallbackHandler()
    is_mw, name, node = h._detect_middleware(
        serialized={},
        name=None,
        metadata={"langgraph_node": "MyCustomMiddleware"},
        tags=[],
    )
    assert is_mw is True
    assert node == "MyCustomMiddleware"


def test_not_middleware_for_agent_node():
    from langchain_trace_cb.callback import TraceCallbackHandler
    h = TraceCallbackHandler()
    is_mw, _, node = h._detect_middleware(
        serialized={"id": ["langchain", "agent"]},
        name="agent",
        metadata={"langgraph_node": "agent"},
        tags=[],
    )
    assert is_mw is False
    assert node == "agent"


def test_not_middleware_for_tools_node():
    from langchain_trace_cb.callback import TraceCallbackHandler
    h = TraceCallbackHandler()
    is_mw, _, _ = h._detect_middleware(
        serialized={"id": ["langchain", "tools"]},
        name="tools",
        metadata={"langgraph_node": "tools"},
        tags=[],
    )
    assert is_mw is False
```

- [ ] **Step 4: 跑全部测试**

Run: `cd client && python -m pytest tests/ -q`
Expected: 8/8 通过

- [ ] **Step 5: 重新打包 0.4.0**

修改 `client/pyproject.toml` version 为 `0.4.0`，然后：
```bash
cd client && rm -rf dist build && python -m build
```

---

## Task 4: 前端类型扩展

**Files:**
- Modify: `frontend/src/types/trace.ts`

- [ ] **Step 1: `TraceEvent` 加 3 字段**

第 10-23 行 `TraceEvent` 接口末尾加：
```typescript
is_middleware?: boolean;
middleware_name?: string | null;
node_name?: string | null;
```

- [ ] **Step 2: TSC 检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 通过

---

## Task 5: 前端 CallTree middleware 视觉识别

**Files:**
- Modify: `frontend/src/components/CallTree.tsx`

- [ ] **Step 1: 加 middleware 类型识别函数**

文件顶部 import 增加：
```typescript
import { Boxes, Cpu, Wrench, Search, Bot, FileText, Settings2 } from "lucide-react";
```

`KIND_META` 字典末尾加：
```typescript
middleware: { label: "Middleware", icon: Settings2, color: "text-orange-700", bg: "bg-orange-100" },
```

`classifyEvent` 函数（约 38 行）末尾加：
```typescript
if (ev.metadata?.is_middleware || ev.metadata?.node_name) {
  // 不强制覆盖已有分类——只作为后备
}
```

在 `buildRunTree` 内聚合 RunNode 时（约 145 行附近），加字段：
```typescript
is_middleware: boolean = false,
middleware_name: string | None = null,
node_name: string | None = null,
```

聚合处增加：
```typescript
is_middleware: startEv.metadata?.is_middleware === true || endEv?.metadata?.is_middleware === true,
middleware_name: startEv.metadata?.middleware_name ?? null,
node_name: startEv.metadata?.node_name ?? null,
```

- [ ] **Step 2: 节点卡片显示 middleware 标识**

`RunNodeCard` 内（kind 渲染后），加：
```tsx
{node.is_middleware && (
  <span className="inline-flex items-center gap-1 text-[10px] mono px-1.5 py-0.5 rounded bg-orange-100 text-orange-700 shrink-0">
    <Settings2 className="w-3 h-3" /> {node.middleware_name || "Middleware"}
  </span>
)}
```

节点卡片左右边框加重（middleware 风格）：
```tsx
className={`rounded-lg border bg-white transition-all hover:shadow-sm ${
  node.is_middleware
    ? "border-orange-300 ring-1 ring-orange-200"
    : node.status === "failed" ? "border-red-200" : "border-slate-200"
}`}
```

- [ ] **Step 3: TSC 检查**

Run: `cd frontend && npx tsc --noEmit`
Expected: 通过

---

## Task 6: 前端时间线 middleware 标记

**Files:**
- Modify: `frontend/src/components/EventTimeline.tsx`

- [ ] **Step 1: 渲染 middleware 事件特殊样式**

找到事件项渲染（按 event_type 给颜色 badge 处），对 `is_middleware` 事件增加：
```tsx
{ev.is_middleware && (
  <span className="ml-1.5 inline-flex items-center gap-1 text-[10px] font-medium px-1.5 py-0.5 rounded bg-orange-100 text-orange-700">
    <Settings2 className="w-3 h-3" />
    {ev.middleware_name || "Middleware"}
  </span>
)}
{ev.node_name && !ev.is_middleware && (
  <span className="ml-1.5 text-[10px] mono px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
    {ev.node_name}
  </span>
)}
```

事件整体时间线条颜色：middleware 事件用 `bg-orange-400`，其它保持。

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: 通过

---

## Task 7: 前端消息流 middleware 边界横幅

**Files:**
- Modify: `frontend/src/components/MessageFlow.tsx`

- [ ] **Step 1: 在 middleware 事件前插入横幅**

消息流渲染时，按 events 顺序同步推进 `middlewareCursor`。每当 `is_middleware && event_type === 'chain_start'` 时，在下一个 HumanMessage/AI/Tool 之前插入横幅。

简化为：渲染消息前，从 `events` 找到 `is_middleware` 且尚未显示的，按时间序展示在消息组上方。

实现：在 `MessageFlow` 组件内从 props 取 `events`，按时间排序，找到 `is_middleware` 的 chain_start，按消息流分组插入：

```tsx
{/* middleware 边界横幅 */}
{messageGroups.map((group, gi) => (
  <React.Fragment key={gi}>
    {group.precedingMiddleware?.map(mw => (
      <div key={mw.event_id} className="my-2 mx-4 px-3 py-2 rounded-md bg-orange-50 border border-orange-200 text-xs text-orange-700 flex items-center gap-2">
        <Settings2 className="w-3.5 h-3.5" />
        <span className="font-medium">Middleware:</span>
        <span className="mono">{mw.middleware_name || mw.node_name}</span>
        {mw.node_name && mw.node_name !== mw.middleware_name && (
          <span className="text-orange-500">({mw.node_name})</span>
        )}
      </div>
    ))}
    {/* 消息气泡 */}
  </React.Fragment>
))}
```

`messageGroups` 切分逻辑：根据每个消息的时间戳与 middleware 事件时间戳的关系分组。

- [ ] **Step 2: TSC**

Run: `cd frontend && npx tsc --noEmit`
Expected: 通过

---

## Task 8: 前端详情 Header middleware 徽章

**Files:**
- Modify: `frontend/src/components/TraceDetailHeader.tsx`

- [ ] **Step 1: 统计 events 中的 middleware 列表**

接收 `events` prop，提取 `middleware_name` 去重计数：
```typescript
const middlewareSet = new Set<string>();
for (const ev of events) {
  if (ev.is_middleware && ev.middleware_name) middlewareSet.add(ev.middleware_name);
}
```

- [ ] **Step 2: 显示徽章**

Header 已有 `thread_id` 徽章的位置后，加：
```tsx
{Array.from(middlewareSet).map(mw => (
  <span key={mw} className="inline-flex items-center gap-1 text-[11px] mono px-2 py-0.5 rounded bg-orange-100 text-orange-700 border border-orange-200">
    <Settings2 className="w-3 h-3" /> {mw}
  </span>
))}
```

---

## Task 9: 端到端测试

**Files:**
- 无（手动验证）

- [ ] **Step 1: 装 0.4.0 wheel**

```bash
pip uninstall langchain-trace-cb -y
pip install C:\Workspace\Development\Study\study_langchain\client\dist\langchain_trace_cb-0.4.0-py3-none-any.whl
```

- [ ] **Step 2: 写一个使用 PIIMiddleware 的 agent 脚本**

`backend/tests/manual_middleware_test.py`：
```python
import os, time
from uuid import uuid4
from langchain_trace_cb import TraceCallbackHandler

# 模拟一个 PIIMiddleware 触发的 chain event
h = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="middleware-test",
)
rid = uuid4()
h.on_chain_start(
    {"id": ["langchain", "PIIMiddleware"]},
    {"input": "我的手机号 13800138000"},
    run_id=rid,
    metadata={"langgraph_node": "PIIMiddleware"},
    tags=["langchain:middleware"],
)
time.sleep(0.1)
h.on_chain_end({"output": "我的手机号 <REDACTED>"}, run_id=rid)
print("sent")
```

Run: `python backend/tests/manual_middleware_test.py`
Expected: 推送 1 条 trace，count +1

- [ ] **Step 3: 验证后端**

```bash
curl http://[::1]:8000/api/v1/traces/count/total
```
Expected: 数字 +1

- [ ] **Step 4: 验证前端**

刷新 http://localhost:5173，找到 middleware-test 详情：
- 调用树：根节点卡片有橙色边框 + "Middleware" 徽章
- 时间线：PIIMiddleware 事件用橙色
- 消息流：在 PIIMiddleware 触发的消息前有橙色横幅
- Header：显示 `PIIMiddleware` 徽章

---

## Task 10: 文档更新

**Files:**
- Modify: `docs/AI-Agent接入说明.md`
- Modify: `docs/开发环境启动.md`

- [ ] **Step 1: AI-Agent 接入说明加 Middleware 章节**

在 "使用示例" 后加：
```markdown
## Middleware 追踪

`create_agent(..., middleware=[...])` 中间件会被自动追踪：

- **内置 middleware**（PIIMiddleware、SummarizationMiddleware 等）：通过 `langgraph_node` 识别
- **自定义 middleware**（继承 AgentMiddleware）：通过类名 `Middleware` 后缀识别；或加 `tags=["langchain:middleware:YourName"]`

前端识别方式：
- 调用树：橙色边框 + 齿轮图标 + middleware 类名徽章
- 时间线：橙色节点 + node_name 标签
- 消息流：橙色横幅标记 middleware 边界
- Header：middleware 列表徽章

支持的 LangChain 版本：>= 1.0
```

- [ ] **Step 2: 开发环境启动加测试段落**

加：
```markdown
### 测试 middleware 追踪

```bash
python backend/tests/manual_middleware_test.py
```

刷新 http://localhost:5173 查看详情。
```

---

## Self-Review

**1. Spec 覆盖:**
- 前端识别 middleware 节点 ✓ (Task 5)
- 时间线标记 ✓ (Task 6)
- 消息流边界 ✓ (Task 7)
- Header 徽章 ✓ (Task 8)
- 文档说明 ✓ (Task 10)
- 端到端验证 ✓ (Task 9)
- 启发式识别（类名后缀 / tag / node_name）✓ (Task 3)

**2. 占位符扫描:** 无 "TBD"/"TODO"/"fill in" — 全部代码完整。

**3. 类型一致:** `is_middleware` / `middleware_name` / `node_name` 三个字段在 Event 模型 (Task 1) → EventPayload (Task 2) → TraceEvent (Task 4) → CallTree (Task 5) / Timeline (Task 6) / MessageFlow (Task 7) / Header (Task 8) 全部命名一致。

**OK，开始执行。**
