# LangChain Trace Logger 实现计划

> **For agentic workers:** 本计划按任务拆分，使用 checkbox (`- [ ]`) 跟踪进度。按顺序执行任务，每个任务完成后提交一次。

**Goal:** 构建一个接收、存储、展示 LangChain 调用轨迹的日志系统，AI Agent 通过自定义 callback 将轨迹推送到后端，前端以时间线/调用树/消息流的形式可视化。

**Architecture:** 采用 **HTTP API 推送** 架构（非 MCP、非直连数据库）。AI Agent 安装一个轻量 callback 包，在 `invoke` 执行期间采集事件，结束时一次性 POST 完整 trace 到后端。后端用 FastAPI + 仓储模式（Repository Pattern）抽象存储，默认内存存储，可扩展文件/数据库。前端 React + Vite + TypeScript + TailwindCSS + shadcn/ui + TanStack Query，展示列表与详情（时间线 + 调用树 + 消息流）。

**Tech Stack:**
- 后端: Python 3.11+, FastAPI, Pydantic v2, Uvicorn, httpx (测试), pytest
- Callback 客户端: Python, langchain-core, httpx (可选 requests)
- 前端: React 18, Vite, TypeScript, TailwindCSS, shadcn/ui, TanStack Query v5, React Router v6, lucide-react

---

## 一、架构决策说明

### 为什么选 HTTP API 推送（而非 MCP / 直连数据库）

| 方案 | 优点 | 缺点 | 结论 |
|------|------|------|------|
| **HTTP API 推送** ✅ | 解耦清晰；存储抽象在后端；Agent 只需一个轻量 callback；易扩展存储；非阻塞 | 需后端在线 | **采用** |
| MCP 服务 | 标准化工具调用 | 为 LLM 工具调用设计，不适合日志推送；增加 stdio/SSE 传输复杂度 | 不采用 |
| Agent 直连数据库 | 无中间层 | Agent 耦合 DB schema；schema 变更需改所有 Agent；无校验/转换中心 | 不采用 |

### 数据流

```
AI Agent (langchain v1.3.11)
   │  agent.invoke({...}, config={"callbacks": [TraceCallbackHandler(endpoint=...)]})
   ▼
TraceCallbackHandler 采集事件 ── HTTP POST /api/v1/traces ──▶ FastAPI 后端
                                                                 │
                                                                 ▼
                                                          Repository（内存/文件/可扩展DB）
                                                                 ▲
                                                                 │ HTTP GET
                                                          React 前端（列表 + 详情）
```

### 核心数据模型

```python
# Trace（一次 invoke = 一个 trace）
{
    "trace_id": "uuid",
    "name": "runnable 名称",
    "start_time": "2026-07-04T10:00:00.123",
    "end_time": "2026-07-04T10:00:02.456",
    "duration_ms": 2333,
    "status": "succeeded|failed",
    "input": {...},          # invoke 输入
    "output": {...},         # invoke 输出
    "messages": [...],       # 最终消息列表（JSON 序列化）
    "structured_response": {...},
    "metadata": {...},
    "tags": [...],
    "error": null | {"type": "...", "message": "..."},
    "events": [Event, ...]   # 事件列表
}

# Event（每个回调事件）
{
    "event_id": "uuid",
    "run_id": "uuid",            # langchain run_id
    "parent_run_id": "uuid|null",
    "event_type": "llm_start|chat_model_start|llm_end|llm_new_token|chain_start|chain_end|tool_start|tool_end|tool_error|chain_error|llm_error|agent_action|agent_finish|retriever_start|retriever_end|text",
    "timestamp": "ISO8601",
    "name": "runnable 名",
    "serialized": {...},         # runnable 序列化信息
    "inputs": {...},
    "outputs": {...},
    "metadata": {...},
    "tags": [...],
    "level": "info|warn|error"
}
```

事件通过 `run_id` / `parent_run_id` 构成调用树；通过 `timestamp` 构成时间线；通过 `event_type` 区分类型。

---

## 二、文件结构

```
study_langchain/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                    # FastAPI 应用入口
│   │   ├── config.py                  # 配置（Settings）
│   │   ├── dependencies.py            # 依赖注入（获取 repository）
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── router.py          # 聚合路由
│   │   │       └── traces.py          # trace 相关端点
│   │   ├── models/
│   │   │   ├── __init__.py
│   │   │   ├── event.py               # Event pydantic 模型
│   │   │   └── trace.py               # Trace pydantic 模型
│   │   ├── repositories/
│   │   │   ├── __init__.py
│   │   │   ├── base.py                # TraceRepository ABC
│   │   │   ├── memory.py              # InMemoryRepository
│   │   │   └── file.py                # FileRepository（JSON 文件）
│   │   └── services/
│   │       ├── __init__.py
│   │       └── trace_service.py       # 业务逻辑层
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py
│   │   ├── test_models.py
│   │   ├── test_memory_repo.py
│   │   ├── test_file_repo.py
│   │   ├── test_trace_service.py
│   │   └── test_api_traces.py
│   ├── pyproject.toml
│   └── .env.example
├── client/                            # AI Agent 安装的 callback 包
│   ├── langchain_trace_cb/
│   │   ├── __init__.py                # 导出 TraceCallbackHandler
│   │   ├── callback.py                # BaseCallbackHandler 实现
│   │   ├── client.py                  # HTTP 客户端
│   │   └── models.py                  # 事件/trace 序列化模型
│   ├── tests/
│   │   ├── __init__.py
│   │   └── test_callback.py
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── index.css
│   │   ├── lib/
│   │   │   ├── api.ts                 # API 客户端
│   │   │   └── utils.ts               # cn() 等工具
│   │   ├── types/
│   │   │   └── trace.ts               # TS 类型定义
│   │   ├── hooks/
│   │   │   └── useTraces.ts           # TanStack Query hooks
│   │   ├── components/
│   │   │   ├── ui/                    # shadcn/ui 组件
│   │   │   ├── TraceListTable.tsx
│   │   │   ├── TraceDetailHeader.tsx
│   │   │   ├── EventTimeline.tsx      # 时间线视图
│   │   │   ├── CallTree.tsx           # 调用树视图
│   │   │   ├── EventCard.tsx          # 单事件卡片
│   │   │   ├── MessageFlow.tsx        # 消息流视图
│   │   │   └── JsonViewer.tsx         # JSON 折叠展示
│   │   └── pages/
│   │       ├── TraceListPage.tsx
│   │       └── TraceDetailPage.tsx
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── docs/
│   ├── plans/
│   │   └── 2026-07-04-langchain-trace-logger.md  # 本文件
│   ├── 开发环境启动.md
│   └── AI-Agent接入说明.md
└── README.md
```

---

## 三、实现任务

### Task 1: 后端项目脚手架与配置

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/app/__init__.py`
- Create: `backend/app/config.py`
- Create: `backend/.env.example`
- Create: `backend/tests/__init__.py`
- Create: `backend/tests/conftest.py`

- [ ] **Step 1: 创建 `backend/pyproject.toml`**

```toml
[project]
name = "langchain-trace-backend"
version = "0.1.0"
description = "LangChain trace logging backend"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-multipart>=0.0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["app*"]
```

- [ ] **Step 2: 创建 `backend/app/__init__.py`**

```python
"""LangChain Trace Logger Backend."""
```

- [ ] **Step 3: 创建 `backend/app/config.py`**

```python
"""应用配置。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用配置，从环境变量读取。"""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="TRACE_", case_sensitive=False
    )

    # 存储后端类型: memory | file
    storage_backend: str = "memory"
    # file 存储时使用的目录
    file_storage_dir: str = "./data/traces"
    # CORS 允许的前端来源
    cors_origins: list[str] = ["http://localhost:5173"]
    # API 前缀
    api_prefix: str = "/api/v1"


settings = Settings()
```

- [ ] **Step 4: 创建 `backend/.env.example`**

```env
TRACE_STORAGE_BACKEND=memory
TRACE_FILE_STORAGE_DIR=./data/traces
TRACE_CORS_ORIGINS=["http://localhost:5173"]
TRACE_API_PREFIX=/api/v1
```

- [ ] **Step 5: 创建 `backend/tests/__init__.py` 与 `backend/tests/conftest.py`**

`tests/__init__.py`:
```python
```

`tests/conftest.py`:
```python
"""pytest 公共 fixtures。"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.dependencies import get_repository
from app.repositories.memory import InMemoryRepository


@pytest.fixture
def memory_repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def client(memory_repo) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: memory_repo
    return TestClient(app)
```

- [ ] **Step 6: 安装依赖并验证**

Run: `cd backend && pip install -e ".[dev]"`
Expected: 安装成功，无错误

- [ ] **Step 7: 提交**

```bash
git add backend/
git commit -m "chore: scaffold backend project with config and test setup"
```

---

### Task 2: 数据模型（Pydantic）

**Files:**
- Create: `backend/app/models/__init__.py`
- Create: `backend/app/models/event.py`
- Create: `backend/app/models/trace.py`
- Create: `backend/tests/test_models.py`

- [ ] **Step 1: 创建 `backend/app/models/__init__.py`**

```python
"""数据模型。"""
from app.models.event import Event, EventType
from app.models.trace import Trace, TraceStatus, TraceCreate

__all__ = ["Event", "EventType", "Trace", "TraceStatus", "TraceCreate"]
```

- [ ] **Step 2: 创建 `backend/app/models/event.py`**

```python
"""事件模型。"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    LLM_START = "llm_start"
    CHAT_MODEL_START = "chat_model_start"
    LLM_END = "llm_end"
    LLM_NEW_TOKEN = "llm_new_token"
    LLM_ERROR = "llm_error"
    CHAIN_START = "chain_start"
    CHAIN_END = "chain_end"
    CHAIN_ERROR = "chain_error"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    TOOL_ERROR = "tool_error"
    RETRIEVER_START = "retriever_start"
    RETRIEVER_END = "retriever_end"
    AGENT_ACTION = "agent_action"
    AGENT_FINISH = "agent_finish"
    TEXT = "text"


class Event(BaseModel):
    """单个回调事件。"""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    parent_run_id: str | None = None
    event_type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    name: str | None = None
    serialized: dict[str, Any] | None = None
    inputs: Any | None = None
    outputs: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    level: str = "info"
```

- [ ] **Step 3: 创建 `backend/app/models/trace.py`**

```python
"""Trace 模型。"""
from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.event import Event


class TraceStatus(str, Enum):
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class TraceCreate(BaseModel):
    """创建 trace 的请求体。"""

    name: str | None = None
    input: Any | None = None
    output: Any | None = None
    messages: list[Any] = Field(default_factory=list)
    structured_response: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    status: TraceStatus = TraceStatus.SUCCEEDED
    error: dict[str, Any] | None = None
    events: list[Event] = Field(default_factory=list)


class Trace(TraceCreate):
    """完整 trace（含 ID）。"""

    trace_id: str = Field(default_factory=lambda: str(uuid4()))
    duration_ms: int | None = None

    def model_post_init(self, __context: Any) -> None:
        if self.start_time and self.end_time and self.duration_ms is None:
            delta = self.end_time - self.start_time
            self.duration_ms = int(delta.total_seconds() * 1000)
```

- [ ] **Step 4: 写测试 `backend/tests/test_models.py`**

```python
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
```

- [ ] **Step 5: 运行测试验证**

Run: `cd backend && pytest tests/test_models.py -v`
Expected: 3 个测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/models backend/tests/test_models.py
git commit -m "feat: add Event and Trace pydantic models with tests"
```

---

### Task 3: 存储仓储抽象与内存实现

**Files:**
- Create: `backend/app/repositories/__init__.py`
- Create: `backend/app/repositories/base.py`
- Create: `backend/app/repositories/memory.py`
- Create: `backend/tests/test_memory_repo.py`

- [ ] **Step 1: 创建 `backend/app/repositories/__init__.py`**

```python
"""存储仓储层。"""
from app.repositories.base import TraceRepository
from app.repositories.memory import InMemoryRepository

__all__ = ["TraceRepository", "InMemoryRepository"]
```

- [ ] **Step 2: 创建 `backend/app/repositories/base.py`**

```python
"""仓储抽象基类。扩展存储后端时继承此类并实现所有方法。"""
from abc import ABC, abstractmethod

from app.models.trace import Trace, TraceCreate


class TraceRepository(ABC):
    """Trace 存储仓储接口。"""

    @abstractmethod
    async def create(self, trace_create: TraceCreate) -> Trace:
        """创建 trace。"""

    @abstractmethod
    async def get(self, trace_id: str) -> Trace | None:
        """按 ID 获取 trace（含 events）。"""

    @abstractmethod
    async def list(
        self, *, limit: int = 50, offset: int = 0
    ) -> list[Trace]:
        """分页列出 trace（不含 events，仅摘要）。"""

    @abstractmethod
    async def count(self) -> int:
        """总数。"""

    @abstractmethod
    async def delete(self, trace_id: str) -> bool:
        """删除 trace，返回是否删除成功。"""
```

- [ ] **Step 3: 创建 `backend/app/repositories/memory.py`**

```python
"""内存存储实现（默认）。"""
from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


class InMemoryRepository(TraceRepository):
    """线程安全的内存存储。适用于开发与单实例部署。"""

    def __init__(self) -> None:
        self._store: dict[str, Trace] = {}
        self._order: list[str] = []

    async def create(self, trace_create: TraceCreate) -> Trace:
        trace = Trace(**trace_create.model_dump())
        self._store[trace.trace_id] = trace
        self._order.append(trace.trace_id)
        return trace

    async def get(self, trace_id: str) -> Trace | None:
        return self._store.get(trace_id)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Trace]:
        ids = self._order[offset : offset + limit]
        return [self._store[i] for i in ids]

    async def count(self) -> int:
        return len(self._store)

    async def delete(self, trace_id: str) -> bool:
        if trace_id in self._store:
            del self._store[trace_id]
            self._order.remove(trace_id)
            return True
        return False
```

- [ ] **Step 4: 写测试 `backend/tests/test_memory_repo.py`**

```python
"""内存仓储测试。"""
import pytest

from app.models import Event, EventType, TraceCreate
from app.repositories.memory import InMemoryRepository


@pytest.fixture
def repo():
    return InMemoryRepository()


async def test_create_and_get(repo):
    tc = TraceCreate(name="test", input={"q": "hi"})
    created = await repo.create(tc)
    assert created.trace_id
    fetched = await repo.get(created.trace_id)
    assert fetched is not None
    assert fetched.name == "test"


async def test_get_not_found(repo):
    assert await repo.get("missing") is None


async def test_list_pagination(repo):
    for i in range(5):
        await repo.create(TraceCreate(name=f"t{i}"))
    page = await repo.list(limit=2, offset=0)
    assert len(page) == 2
    assert page[0].name == "t0"
    page2 = await repo.list(limit=2, offset=2)
    assert page2[0].name == "t2"


async def test_count(repo):
    await repo.create(TraceCreate(name="a"))
    await repo.create(TraceCreate(name="b"))
    assert await repo.count() == 2


async def test_delete(repo):
    created = await repo.create(TraceCreate(name="x"))
    assert await repo.delete(created.trace_id) is True
    assert await repo.get(created.trace_id) is None
    assert await repo.delete("missing") is False


async def test_create_with_events(repo):
    e = Event(run_id="r1", event_type=EventType.CHAIN_START)
    tc = TraceCreate(name="with-events", events=[e])
    created = await repo.create(tc)
    fetched = await repo.get(created.trace_id)
    assert len(fetched.events) == 1
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && pytest tests/test_memory_repo.py -v`
Expected: 6 个测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/repositories backend/tests/test_memory_repo.py
git commit -m "feat: add TraceRepository ABC and InMemoryRepository with tests"
```

---

### Task 4: 文件存储实现

**Files:**
- Create: `backend/app/repositories/file.py`
- Create: `backend/tests/test_file_repo.py`

- [ ] **Step 1: 创建 `backend/app/repositories/file.py`**

```python
"""JSON 文件存储实现。每个 trace 存为一个 JSON 文件。"""
import json
from pathlib import Path

from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


class FileRepository(TraceRepository):
    """文件存储。每个 trace 一个 .json 文件，按时间倒序读取列表。"""

    def __init__(self, storage_dir: str) -> None:
        self._dir = Path(storage_dir)
        self._dir.mkdir(parents=True, exist_ok=True)

    def _path(self, trace_id: str) -> Path:
        return self._dir / f"{trace_id}.json"

    async def create(self, trace_create: TraceCreate) -> Trace:
        trace = Trace(**trace_create.model_dump())
        self._path(trace.trace_id).write_text(
            trace.model_dump_json(indent=2), encoding="utf-8"
        )
        return trace

    async def get(self, trace_id: str) -> Trace | None:
        p = self._path(trace_id)
        if not p.exists():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        return Trace(**data)

    async def list(self, *, limit: int = 50, offset: int = 0) -> list[Trace]:
        files = sorted(self._dir.glob("*.json"), key=lambda f: f.stat().st_mtime, reverse=True)
        files = files[offset : offset + limit]
        traces: list[Trace] = []
        for f in files:
            data = json.loads(f.read_text(encoding="utf-8"))
            traces.append(Trace(**data))
        return traces

    async def count(self) -> int:
        return len(list(self._dir.glob("*.json")))

    async def delete(self, trace_id: str) -> bool:
        p = self._path(trace_id)
        if p.exists():
            p.unlink()
            return True
        return False
```

- [ ] **Step 2: 写测试 `backend/tests/test_file_repo.py`**

```python
"""文件仓储测试。"""
import pytest

from app.models import TraceCreate
from app.repositories.file import FileRepository


@pytest.fixture
def repo(tmp_path):
    return FileRepository(str(tmp_path / "traces"))


async def test_create_and_get(repo):
    created = await repo.create(TraceCreate(name="file-test"))
    fetched = await repo.get(created.trace_id)
    assert fetched is not None
    assert fetched.name == "file-test"


async def test_list_order(repo):
    import time
    a = await repo.create(TraceCreate(name="a"))
    time.sleep(0.01)
    b = await repo.create(TraceCreate(name="b"))
    result = await repo.list(limit=10)
    assert result[0].name == "b"


async def test_count_and_delete(repo):
    await repo.create(TraceCreate(name="x"))
    assert await repo.count() == 1
    files = list(repo._dir.glob("*.json"))
    await repo.delete(files[0].stem)
    assert await repo.count() == 0
```

- [ ] **Step 3: 运行测试**

Run: `cd backend && pytest tests/test_file_repo.py -v`
Expected: 3 个测试通过

- [ ] **Step 4: 提交**

```bash
git add backend/app/repositories/file.py backend/tests/test_file_repo.py
git commit -m "feat: add FileRepository (JSON file storage) with tests"
```

---

### Task 5: 业务服务层与依赖注入

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/trace_service.py`
- Create: `backend/app/dependencies.py`
- Create: `backend/tests/test_trace_service.py`

- [ ] **Step 1: 创建 `backend/app/services/__init__.py`**

```python
"""业务服务层。"""
from app.services.trace_service import TraceService

__all__ = ["TraceService"]
```

- [ ] **Step 2: 创建 `backend/app/services/trace_service.py`**

```python
"""Trace 业务逻辑层，封装仓储调用。"""
from app.models.trace import Trace, TraceCreate
from app.repositories.base import TraceRepository


class TraceService:
    """Trace 业务服务。"""

    def __init__(self, repository: TraceRepository) -> None:
        self._repo = repository

    async def create_trace(self, payload: TraceCreate) -> Trace:
        return await self._repo.create(payload)

    async def get_trace(self, trace_id: str) -> Trace | None:
        return await self._repo.get(trace_id)

    async def list_traces(self, *, limit: int = 50, offset: int = 0) -> list[Trace]:
        return await self._repo.list(limit=limit, offset=offset)

    async def count_traces(self) -> int:
        return await self._repo.count()

    async def delete_trace(self, trace_id: str) -> bool:
        return await self._repo.delete(trace_id)
```

- [ ] **Step 3: 创建 `backend/app/dependencies.py`**

```python
"""FastAPI 依赖注入。"""
from functools import lru_cache

from app.config import settings
from app.repositories.base import TraceRepository
from app.repositories.memory import InMemoryRepository
from app.repositories.file import FileRepository
from app.services import TraceService


@lru_cache
def get_repository() -> TraceRepository:
    """根据配置返回存储仓储单例。"""
    if settings.storage_backend == "file":
        return FileRepository(settings.file_storage_dir)
    return InMemoryRepository()


def get_trace_service() -> TraceService:
    return TraceService(get_repository())
```

- [ ] **Step 4: 写测试 `backend/tests/test_trace_service.py`**

```python
"""服务层测试。"""
import pytest

from app.models import TraceCreate
from app.repositories.memory import InMemoryRepository
from app.services import TraceService


@pytest.fixture
def service():
    return TraceService(InMemoryRepository())


async def test_create_and_get(service):
    t = await service.create_trace(TraceCreate(name="svc"))
    assert await service.get_trace(t.trace_id) is not None


async def test_list_and_count(service):
    await service.create_trace(TraceCreate(name="a"))
    await service.create_trace(TraceCreate(name="b"))
    assert await service.count_traces() == 2
    assert len(await service.list_traces()) == 2


async def test_delete(service):
    t = await service.create_trace(TraceCreate(name="x"))
    assert await service.delete_trace(t.trace_id) is True
    assert await service.get_trace(t.trace_id) is None
```

- [ ] **Step 5: 运行测试**

Run: `cd backend && pytest tests/test_trace_service.py -v`
Expected: 3 个测试通过

- [ ] **Step 6: 提交**

```bash
git add backend/app/services backend/app/dependencies.py backend/tests/test_trace_service.py
git commit -m "feat: add TraceService and dependency injection"
```

---

### Task 6: API 端点

**Files:**
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/v1/__init__.py`
- Create: `backend/app/api/v1/router.py`
- Create: `backend/app/api/v1/traces.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/test_api_traces.py`

- [ ] **Step 1: 创建 `backend/app/api/__init__.py` 与 `backend/app/api/v1/__init__.py`**

`api/__init__.py`:
```python
```

`api/v1/__init__.py`:
```python
```

- [ ] **Step 2: 创建 `backend/app/api/v1/traces.py`**

```python
"""Trace API 端点。"""
from fastapi import APIRouter, Depends, HTTPException, Query

from app.dependencies import get_trace_service
from app.models.trace import Trace, TraceCreate
from app.services import TraceService

router = APIRouter(prefix="/traces", tags=["traces"])


@router.post("", response_model=Trace, status_code=201)
async def create_trace(
    payload: TraceCreate,
    service: TraceService = Depends(get_trace_service),
) -> Trace:
    """接收一个完整 trace（含事件），保存。"""
    return await service.create_trace(payload)


@router.get("", response_model=list[Trace])
async def list_traces(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    service: TraceService = Depends(get_trace_service),
) -> list[Trace]:
    """分页列出 trace（含 events）。"""
    return await service.list_traces(limit=limit, offset=offset)


@router.get("/{trace_id}", response_model=Trace)
async def get_trace(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> Trace:
    """获取单个 trace 详情（含全部事件）。"""
    trace = await service.get_trace(trace_id)
    if trace is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return trace


@router.delete("/{trace_id}", status_code=204)
async def delete_trace(
    trace_id: str,
    service: TraceService = Depends(get_trace_service),
) -> None:
    """删除 trace。"""
    ok = await service.delete_trace(trace_id)
    if not ok:
        raise HTTPException(status_code=404, detail="trace not found")


@router.get("/count/total")
async def count_traces(
    service: TraceService = Depends(get_trace_service),
) -> dict:
    """获取 trace 总数。"""
    return {"count": await service.count_traces()}
```

- [ ] **Step 3: 创建 `backend/app/api/v1/router.py`**

```python
"""v1 路由聚合。"""
from fastapi import APIRouter

from app.api.v1 import traces

api_router = APIRouter()
api_router.include_router(traces.router)
```

- [ ] **Step 4: 创建 `backend/app/main.py`**

```python
"""FastAPI 应用入口。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="LangChain Trace Logger",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)
    return app


app = create_app()
```

- [ ] **Step 5: 写 API 测试 `backend/tests/test_api_traces.py`**

```python
"""API 端点测试。"""
from app.models import Event, EventType, TraceCreate


def test_create_and_get_trace(client):
    payload = TraceCreate(
        name="test-agent",
        input={"messages": [{"role": "user", "content": "hi"}]},
        output={"result": "hello"},
        events=[
            Event(run_id="r1", event_type=EventType.CHAIN_START, name="agent"),
        ],
    )
    resp = client.post("/api/v1/traces", json=payload.model_dump(mode="json"))
    assert resp.status_code == 201
    trace_id = resp.json()["trace_id"]

    get_resp = client.get(f"/api/v1/traces/{trace_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["name"] == "test-agent"
    assert len(get_resp.json()["events"]) == 1


def test_list_traces(client):
    for i in range(3):
        client.post("/api/v1/traces", json=TraceCreate(name=f"t{i}").model_dump(mode="json"))
    resp = client.get("/api/v1/traces?limit=2&offset=0")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_trace_not_found(client):
    resp = client.get("/api/v1/traces/missing")
    assert resp.status_code == 404


def test_delete_trace(client):
    resp = client.post("/api/v1/traces", json=TraceCreate(name="x").model_dump(mode="json"))
    tid = resp.json()["trace_id"]
    del_resp = client.delete(f"/api/v1/traces/{tid}")
    assert del_resp.status_code == 204
    assert client.get(f"/api/v1/traces/{tid}").status_code == 404


def test_count_traces(client):
    client.post("/api/v1/traces", json=TraceCreate(name="a").model_dump(mode="json"))
    resp = client.get("/api/v1/traces/count/total")
    assert resp.json()["count"] >= 1
```

- [ ] **Step 6: 运行测试**

Run: `cd backend && pytest tests/test_api_traces.py -v`
Expected: 5 个测试通过

- [ ] **Step 7: 启动验证**

Run: `cd backend && uvicorn app.main:app --reload`
Expected: 服务在 http://127.0.0.1:8000 启动，访问 /docs 看到 Swagger

- [ ] **Step 8: 提交**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api_traces.py
git commit -m "feat: add trace API endpoints (create/list/get/delete/count) and FastAPI app"
```

---

### Task 7: Callback 客户端包

**Files:**
- Create: `client/pyproject.toml`
- Create: `client/langchain_trace_cb/__init__.py`
- Create: `client/langchain_trace_cb/models.py`
- Create: `client/langchain_trace_cb/client.py`
- Create: `client/langchain_trace_cb/callback.py`
- Create: `client/tests/__init__.py`
- Create: `client/tests/test_callback.py`

- [ ] **Step 1: 创建 `client/pyproject.toml`**

```toml
[project]
name = "langchain-trace-cb"
version = "0.1.0"
description = "LangChain callback handler that pushes traces to the trace logger backend"
requires-python = ">=3.11"
dependencies = [
    "langchain-core>=0.3.0",
    "httpx>=0.27.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["."]
include = ["langchain_trace_cb*"]
```

- [ ] **Step 2: 创建 `client/langchain_trace_cb/__init__.py`**

```python
"""LangChain Trace Callback 包。

用法:
    from langchain_trace_cb import TraceCallbackHandler

    handler = TraceCallbackHandler(endpoint="http://localhost:8000/api/v1/traces")
    result = agent.invoke({...}, config={"callbacks": [handler]})
"""
from langchain_trace_cb.callback import TraceCallbackHandler
from langchain_trace_cb.client import TraceClient

__all__ = ["TraceCallbackHandler", "TraceClient"]
```

- [ ] **Step 3: 创建 `client/langchain_trace_cb/models.py`**

```python
"""事件/trace 序列化模型（与后端 schema 对齐）。"""
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventPayload(BaseModel):
    """回调事件载荷。"""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    run_id: str
    parent_run_id: str | None = None
    event_type: str
    timestamp: str = Field(default_factory=_now_iso)
    name: str | None = None
    serialized: dict[str, Any] | None = None
    inputs: Any | None = None
    outputs: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    level: str = "info"


class TracePayload(BaseModel):
    """完整 trace 载荷。"""

    name: str | None = None
    input: Any | None = None
    output: Any | None = None
    messages: list[Any] = Field(default_factory=list)
    structured_response: Any | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    start_time: str | None = None
    end_time: str | None = None
    status: str = "succeeded"
    error: dict[str, Any] | None = None
    events: list[EventPayload] = Field(default_factory=list)
```

- [ ] **Step 4: 创建 `client/langchain_trace_cb/client.py`**

```python
"""HTTP 客户端，将 trace 推送到后端。"""
import logging
from typing import Any

import httpx

from langchain_trace_cb.models import TracePayload

logger = logging.getLogger(__name__)


class TraceClient:
    """向后端推送 trace 的 HTTP 客户端。"""

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/traces",
        timeout: float = 5.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._headers = headers or {}

    def send(self, payload: TracePayload) -> dict[str, Any] | None:
        """同步发送 trace。失败时仅记录日志，不抛异常（避免影响 agent）。"""
        try:
            resp = httpx.post(
                self._endpoint,
                content=payload.model_dump_json(),
                headers={"Content-Type": "application/json", **self._headers},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning("Failed to send trace: %s", e)
            return None
```

- [ ] **Step 5: 创建 `client/langchain_trace_cb/callback.py`**

```python
"""LangChain BaseCallbackHandler 实现：采集事件并推送 trace。"""
import logging
from typing import Any
from uuid import UUID

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from langchain_trace_cb.client import TraceClient
from langchain_trace_cb.models import EventPayload, TracePayload

logger = logging.getLogger(__name__)


def _safe(obj: Any) -> Any:
    """尽力将对象转为可 JSON 序列化的结构。"""
    if obj is None:
        return None
    if isinstance(obj, (str, int, float, bool)):
        return obj
    if hasattr(obj, "model_dump"):
        return obj.model_dump()
    if hasattr(obj, "dict"):
        try:
            return obj.dict()
        except Exception:
            pass
    if isinstance(obj, (list, tuple)):
        return [_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _safe(v) for k, v in obj.items()}
    try:
        return str(obj)
    except Exception:
        return None


class TraceCallbackHandler(BaseCallbackHandler):
    """采集 LangChain 调用轨迹并推送到后端。

    用法:
        handler = TraceCallbackHandler(endpoint="http://localhost:8000/api/v1/traces")
        result = agent.invoke({...}, config={"callbacks": [handler]})
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/traces",
        name: str | None = None,
        client: TraceClient | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self._client = client or TraceClient(endpoint=endpoint)
        self._name = name
        self._tags = tags or []
        self._metadata = metadata or {}
        self._events: list[EventPayload] = []
        self._root_run_id: str | None = None
        self._root_name: str | None = name
        self._root_inputs: Any | None = None
        self._failed = False
        self._error: dict[str, Any] | None = None

    # ---- 内部辅助 ----
    def _add(self, event: EventPayload) -> None:
        self._events.append(event)
        if self._root_run_id is None:
            self._root_run_id = event.run_id

    def _rid(self, run_id: UUID) -> str:
        return str(run_id)

    def _pid(self, parent_run_id: UUID | None) -> str | None:
        return str(parent_run_id) if parent_run_id else None

    def _ser_name(self, serialized: dict | None) -> str | None:
        if not serialized:
            return None
        return serialized.get("name") or serialized.get("id", [None])[-1]

    # ---- LLM / Chat ----
    def on_llm_start(
        self, serialized: dict, prompts: list[str], *, run_id: UUID,
        parent_run_id: UUID | None = None, tags: list[str] | None = None,
        metadata: dict | None = None, **kwargs: Any,
    ) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="llm_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"prompts": prompts},
            tags=tags or [], metadata=metadata or {},
        ))

    def on_chat_model_start(
        self, serialized: dict, messages: list[list[BaseMessage]], *, run_id: UUID,
        parent_run_id: UUID | None = None, tags: list[str] | None = None,
        metadata: dict | None = None, **kwargs: Any,
    ) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chat_model_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"messages": _safe(messages)},
            tags=tags or [], metadata=metadata or {},
        ))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID,
                   parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="llm_end", outputs=_safe(response),
        ))

    def on_llm_error(self, error: BaseException, *, run_id: UUID,
                     parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._failed = True
        self._error = {"type": type(error).__name__, "message": str(error)}
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="llm_error", outputs=_safe(error), level="error",
        ))

    def on_llm_new_token(self, token: str, *, run_id: UUID,
                         parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        # 默认不采集 token 流，避免事件过多；如需可在此记录
        pass

    # ---- Chain ----
    def on_chain_start(self, serialized: dict, inputs: dict, *, run_id: UUID,
                       parent_run_id: UUID | None = None, tags: list[str] | None = None,
                       metadata: dict | None = None, **kwargs: Any) -> Any:
        name = self._ser_name(serialized)
        if self._root_run_id is None:
            self._root_run_id = str(run_id)
            self._root_name = name
            self._root_inputs = _safe(inputs)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chain_start", name=name, serialized=serialized,
            inputs=_safe(inputs), tags=tags or [], metadata=metadata or {},
        ))

    def on_chain_end(self, outputs: dict, *, run_id: UUID,
                     parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chain_end", outputs=_safe(outputs),
        ))
        if run_id is not None and str(run_id) == self._root_run_id:
            self._finalize(output=_safe(outputs), outputs_dict=outputs)

    def on_chain_error(self, error: BaseException, *, run_id: UUID,
                       parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._failed = True
        self._error = {"type": type(error).__name__, "message": str(error)}
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chain_error", outputs=_safe(error), level="error",
        ))

    # ---- Tool ----
    def on_tool_start(self, serialized: dict, input_str: str, *, run_id: UUID,
                      parent_run_id: UUID | None = None, tags: list[str] | None = None,
                      metadata: dict | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="tool_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"input": input_str},
            tags=tags or [], metadata=metadata or {},
        ))

    def on_tool_end(self, output: str, *, run_id: UUID,
                    parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="tool_end", outputs=_safe(output),
        ))

    def on_tool_error(self, error: BaseException, *, run_id: UUID,
                      parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._failed = True
        self._error = {"type": type(error).__name__, "message": str(error)}
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="tool_error", outputs=_safe(error), level="error",
        ))

    # ---- Retriever ----
    def on_retriever_start(self, serialized: dict, query: str, *, run_id: UUID,
                           parent_run_id: UUID | None = None, tags: list[str] | None = None,
                           metadata: dict | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="retriever_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"query": query},
            tags=tags or [], metadata=metadata or {},
        ))

    def on_retriever_end(self, documents: Any, *, run_id: UUID,
                         parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="retriever_end", outputs=_safe(documents),
        ))

    # ---- Agent ----
    def on_agent_action(self, action: AgentAction, *, run_id: UUID,
                        parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="agent_action", outputs=_safe(action),
        ))

    def on_agent_finish(self, finish: AgentFinish, *, run_id: UUID,
                        parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="agent_finish", outputs=_safe(finish),
        ))

    # ---- Text ----
    def on_text(self, text: str, *, run_id: UUID,
                parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="text", inputs={"text": text},
        ))

    # ---- 终结与推送 ----
    def _finalize(self, output: Any, outputs_dict: Any) -> None:
        """在根 chain 结束时构造并推送 trace。"""
        import inspect
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        first_ts = self._events[0].timestamp if self._events else now

        # 尝试从输出中提取 messages / structured_response
        messages: list[Any] = []
        structured_response: Any | None = None
        if isinstance(outputs_dict, dict):
            msgs = outputs_dict.get("messages")
            if msgs:
                messages = _safe(msgs) or []
            structured_response = _safe(outputs_dict.get("structured_response"))

        payload = TracePayload(
            name=self._root_name or self._name,
            input=_safe(self._root_inputs),
            output=output,
            messages=messages,
            structured_response=structured_response,
            metadata=self._metadata,
            tags=self._tags,
            start_time=first_ts,
            end_time=now,
            status="failed" if self._failed else "succeeded",
            error=self._error,
            events=self._events,
        )
        self._client.send(payload)
        # 重置以支持 handler 复用
        self._events = []
        self._root_run_id = None
        self._root_inputs = None
        self._failed = False
        self._error = None
```

- [ ] **Step 6: 创建 `client/tests/__init__.py` 与 `client/tests/test_callback.py`**

`tests/__init__.py`:
```python
```

`tests/test_callback.py`:
```python
"""Callback handler 测试。"""
from unittest.mock import MagicMock
from uuid import uuid4

from langchain_trace_cb import TraceCallbackHandler
from langchain_trace_cb.models import TracePayload


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
```

- [ ] **Step 7: 安装并测试**

Run: `cd client && pip install -e ".[dev]" && pytest tests -v`
Expected: 3 个测试通过

- [ ] **Step 8: 提交**

```bash
git add client/
git commit -m "feat: add langchain_trace_cb client package with TraceCallbackHandler"
```

---

### Task 8: 前端脚手架与依赖

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/index.html`
- Create: `frontend/vite.config.ts`
- Create: `frontend/tsconfig.json`
- Create: `frontend/tsconfig.node.json`
- Create: `frontend/tailwind.config.js`
- Create: `frontend/postcss.config.js`
- Create: `frontend/src/main.tsx`
- Create: `frontend/src/index.css`
- Create: `frontend/src/App.tsx`
- Create: `frontend/src/lib/utils.ts`

- [ ] **Step 1: 创建 `frontend/package.json`**

```json
{
  "name": "langchain-trace-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.26.0",
    "@tanstack/react-query": "^5.51.0",
    "lucide-react": "^0.428.0",
    "clsx": "^2.1.1",
    "tailwind-merge": "^2.5.2",
    "class-variance-authority": "^0.7.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.3",
    "@types/react-dom": "^18.3.0",
    "@vitejs/plugin-react": "^4.3.1",
    "typescript": "^5.5.4",
    "vite": "^5.4.0",
    "tailwindcss": "^3.4.10",
    "postcss": "^8.4.41",
    "autoprefixer": "^10.4.20"
  }
}
```

- [ ] **Step 2: 创建配置文件**

`frontend/vite.config.ts`:
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { "@": path.resolve(__dirname, "./src") },
  },
  server: {
    port: 5173,
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

`frontend/tsconfig.json`:
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
```

`frontend/tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
```

`frontend/index.html`:
```html
<!doctype html>
<html lang="zh-CN">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>LangChain Trace Logger</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: 创建 Tailwind 与 PostCSS 配置**

`frontend/tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
};
```

`frontend/postcss.config.js`:
```javascript
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 4: 创建入口文件**

`frontend/src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  @apply bg-slate-50 text-slate-900;
}
```

`frontend/src/lib/utils.ts`:
```typescript
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

`frontend/src/main.tsx`:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import App from "./App";
import "./index.css";

const queryClient = new QueryClient({
  defaultOptions: { queries: { refetchOnWindowFocus: false } },
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
```

`frontend/src/App.tsx`:
```tsx
import { Routes, Route } from "react-router-dom";
import TraceListPage from "./pages/TraceListPage";
import TraceDetailPage from "./pages/TraceDetailPage";

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<TraceListPage />} />
      <Route path="/traces/:traceId" element={<TraceDetailPage />} />
    </Routes>
  );
}
```

- [ ] **Step 5: 安装依赖并验证启动**

Run: `cd frontend && npm install`
Run: `cd frontend && npm run dev`
Expected: 在 http://localhost:5173 启动（页面可能因页面文件未创建而报错，下一步创建）

- [ ] **Step 6: 提交**

```bash
git add frontend/
git commit -m "chore: scaffold frontend with Vite + React + Tailwind + TanStack Query"
```

---

### Task 9: 前端类型与 API 客户端

**Files:**
- Create: `frontend/src/types/trace.ts`
- Create: `frontend/src/lib/api.ts`
- Create: `frontend/src/hooks/useTraces.ts`

- [ ] **Step 1: 创建 `frontend/src/types/trace.ts`**

```typescript
export type EventType =
  | "llm_start" | "chat_model_start" | "llm_end" | "llm_new_token" | "llm_error"
  | "chain_start" | "chain_end" | "chain_error"
  | "tool_start" | "tool_end" | "tool_error"
  | "retriever_start" | "retriever_end"
  | "agent_action" | "agent_finish" | "text";

export type TraceStatus = "running" | "succeeded" | "failed";

export interface TraceEvent {
  event_id: string;
  run_id: string;
  parent_run_id: string | null;
  event_type: EventType;
  timestamp: string;
  name?: string | null;
  serialized?: Record<string, unknown> | null;
  inputs?: unknown;
  outputs?: unknown;
  metadata: Record<string, unknown>;
  tags: string[];
  level: string;
}

export interface Trace {
  trace_id: string;
  name?: string | null;
  input?: unknown;
  output?: unknown;
  messages: unknown[];
  structured_response?: unknown;
  metadata: Record<string, unknown>;
  tags: string[];
  start_time?: string | null;
  end_time?: string | null;
  duration_ms?: number | null;
  status: TraceStatus;
  error?: { type: string; message: string } | null;
  events: TraceEvent[];
}
```

- [ ] **Step 2: 创建 `frontend/src/lib/api.ts`**

```typescript
import type { Trace } from "@/types/trace";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!resp.ok) {
    throw new Error(`API ${resp.status}: ${await resp.text()}`);
  }
  if (resp.status === 204) return undefined as T;
  return resp.json() as Promise<T>;
}

export const api = {
  listTraces: (limit = 50, offset = 0) =>
    request<Trace[]>(`/traces?limit=${limit}&offset=${offset}`),
  getTrace: (id: string) => request<Trace>(`/traces/${id}`),
  deleteTrace: (id: string) =>
    request<void>(`/traces/${id}`, { method: "DELETE" }),
  countTraces: () => request<{ count: number }>(`/traces/count/total`),
};
```

- [ ] **Step 3: 创建 `frontend/src/hooks/useTraces.ts`**

```typescript
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";

export function useTraces(limit = 50, offset = 0) {
  return useQuery({
    queryKey: ["traces", limit, offset],
    queryFn: () => api.listTraces(limit, offset),
  });
}

export function useTrace(traceId: string) {
  return useQuery({
    queryKey: ["trace", traceId],
    queryFn: () => api.getTrace(traceId),
    enabled: !!traceId,
  });
}

export function useDeleteTrace() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteTrace(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["traces"] }),
  });
}
```

- [ ] **Step 4: 提交**

```bash
git add frontend/src/types frontend/src/lib frontend/src/hooks
git commit -m "feat(frontend): add trace types, API client and query hooks"
```

---

### Task 10: 前端页面与可视化组件

**Files:**
- Create: `frontend/src/pages/TraceListPage.tsx`
- Create: `frontend/src/pages/TraceDetailPage.tsx`
- Create: `frontend/src/components/TraceListTable.tsx`
- Create: `frontend/src/components/TraceDetailHeader.tsx`
- Create: `frontend/src/components/EventTimeline.tsx`
- Create: `frontend/src/components/CallTree.tsx`
- Create: `frontend/src/components/EventCard.tsx`
- Create: `frontend/src/components/MessageFlow.tsx`
- Create: `frontend/src/components/JsonViewer.tsx`

- [ ] **Step 1: 创建 `frontend/src/components/JsonViewer.tsx`**

```tsx
import { useState } from "react";
import { ChevronRight, ChevronDown } from "lucide-react";

interface Props {
  data: unknown;
  label?: string;
  defaultOpen?: boolean;
}

export default function JsonViewer({ data, label, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const json = (() => {
    try {
      return JSON.stringify(data, null, 2);
    } catch {
      return String(data);
    }
  })();

  return (
    <div className="border border-slate-200 rounded-md bg-slate-50">
      <button
        className="flex items-center w-full px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-4 h-4 mr-1" /> : <ChevronRight className="w-4 h-4 mr-1" />}
        {label ?? "JSON"}
      </button>
      {open && (
        <pre className="px-3 py-2 text-xs overflow-auto max-h-96 font-mono text-slate-800">
          {json}
        </pre>
      )}
    </div>
  );
}
```

- [ ] **Step 2: 创建 `frontend/src/components/EventCard.tsx`**

```tsx
import type { TraceEvent } from "@/types/trace";
import JsonViewer from "./JsonViewer";

const TYPE_STYLES: Record<string, string> = {
  llm_start: "bg-blue-100 text-blue-700",
  chat_model_start: "bg-blue-100 text-blue-700",
  llm_end: "bg-indigo-100 text-indigo-700",
  chain_start: "bg-emerald-100 text-emerald-700",
  chain_end: "bg-teal-100 text-teal-700",
  tool_start: "bg-amber-100 text-amber-700",
  tool_end: "bg-yellow-100 text-yellow-700",
  agent_action: "bg-purple-100 text-purple-700",
  agent_finish: "bg-fuchsia-100 text-fuchsia-700",
  text: "bg-slate-100 text-slate-700",
  retriever_start: "bg-cyan-100 text-cyan-700",
  retriever_end: "bg-sky-100 text-sky-700",
};

const ERROR_TYPES = ["llm_error", "chain_error", "tool_error"];

interface Props {
  event: TraceEvent;
  depth: number;
}

export default function EventCard({ event, depth }: Props) {
  const isError = ERROR_TYPES.includes(event.event_type);
  const style = isError
    ? "bg-red-100 text-red-700"
    : TYPE_STYLES[event.event_type] ?? "bg-slate-100 text-slate-700";

  return (
    <div
      className="border border-slate-200 rounded-md bg-white p-3 shadow-sm"
      style={{ marginLeft: depth * 24 }}
    >
      <div className="flex items-center gap-2 flex-wrap">
        <span className={`text-xs font-mono px-2 py-0.5 rounded ${style}`}>
          {event.event_type}
        </span>
        {event.name && (
          <span className="text-sm font-semibold text-slate-800">{event.name}</span>
        )}
        <span className="text-xs text-slate-500 ml-auto font-mono">
          {new Date(event.timestamp).toLocaleString("zh-CN", { hour12: false })}
        </span>
      </div>
      <div className="mt-2 space-y-1.5">
        {event.inputs !== undefined && event.inputs !== null && (
          <JsonViewer data={event.inputs} label="输入" />
        )}
        {event.outputs !== undefined && event.outputs !== null && (
          <JsonViewer data={event.outputs} label="输出" />
        )}
        {event.tags.length > 0 && (
          <div className="flex gap-1 flex-wrap">
            {event.tags.map((t, i) => (
              <span key={i} className="text-xs px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                #{t}
              </span>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 创建 `frontend/src/components/CallTree.tsx`**

```tsx
import type { TraceEvent } from "@/types/trace";
import EventCard from "./EventCard";

interface Props {
  events: TraceEvent[];
}

interface TreeNode {
  event: TraceEvent;
  children: TreeNode[];
}

function buildTree(events: TraceEvent[]): TreeNode[] {
  const byId = new Map<string, TreeNode>();
  const roots: TreeNode[] = [];
  for (const e of events) {
    byId.set(e.run_id, { event: e, children: [] });
  }
  for (const e of events) {
    const node = byId.get(e.run_id)!;
    if (e.parent_run_id && byId.has(e.parent_run_id)) {
      byId.get(e.parent_run_id)!.children.push(node);
    } else {
      roots.push(node);
    }
  }
  return roots;
}

function renderNode(node: TreeNode, depth: number): React.ReactNode[] {
  return [
    <EventCard key={node.event.event_id} event={node.event} depth={depth} />,
    ...node.children.flatMap((c) => renderNode(c, depth + 1)),
  ];
}

export default function CallTree({ events }: Props) {
  const roots = buildTree(events);
  return (
    <div className="space-y-2">
      {roots.length === 0 && <p className="text-sm text-slate-500">无事件</p>}
      {roots.flatMap((r) => renderNode(r, 0))}
    </div>
  );
}
```

- [ ] **Step 4: 创建 `frontend/src/components/EventTimeline.tsx`**

```tsx
import type { TraceEvent } from "@/types/trace";
import EventCard from "./EventCard";

interface Props {
  events: TraceEvent[];
}

export default function EventTimeline({ events }: Props) {
  const sorted = [...events].sort(
    (a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime()
  );
  return (
    <div className="space-y-2">
      {sorted.length === 0 && <p className="text-sm text-slate-500">无事件</p>}
      {sorted.map((e) => (
        <EventCard key={e.event_id} event={e} depth={0} />
      ))}
    </div>
  );
}
```

- [ ] **Step 5: 创建 `frontend/src/components/MessageFlow.tsx`**

```tsx
interface Message {
  id?: string;
  content?: unknown;
  type?: string;
  _type?: string;
  name?: string;
  tool_call_id?: string;
  tool_calls?: unknown[];
}

interface Props {
  messages: unknown[];
  structuredResponse?: unknown;
}

function getType(m: Message): string {
  return m.type ?? m._type ?? "unknown";
}

function getContentText(content: unknown): string {
  if (typeof content === "string") return content;
  try {
    return JSON.stringify(content, null, 2);
  } catch {
    return String(content);
  }
}

const TYPE_LABEL: Record<string, { label: string; color: string; align: string }> = {
  human: { label: "用户", color: "bg-blue-500", align: "self-end" },
  ai: { label: "AI", color: "bg-emerald-500", align: "self-start" },
  AIMessage: { label: "AI", color: "bg-emerald-500", align: "self-start" },
  HumanMessage: { label: "用户", color: "bg-blue-500", align: "self-end" },
  tool: { label: "工具", color: "bg-amber-500", align: "self-center" },
  ToolMessage: { label: "工具", color: "bg-amber-500", align: "self-center" },
  system: { label: "系统", color: "bg-slate-500", align: "self-center" },
};

export default function MessageFlow({ messages, structuredResponse }: Props) {
  const msgs = (messages ?? []) as Message[];
  return (
    <div className="space-y-3">
      <div className="flex flex-col gap-2">
        {msgs.map((m, i) => {
          const t = getType(m);
          const conf = TYPE_LABEL[t] ?? { label: t, color: "bg-slate-400", align: "self-start" };
          return (
            <div key={m.id ?? i} className={`flex flex-col ${conf.align} max-w-[80%]`}>
              <div className="flex items-center gap-2 mb-0.5">
                <span className={`w-2 h-2 rounded-full ${conf.color}`} />
                <span className="text-xs font-medium text-slate-600">
                  {conf.label}
                  {m.name ? ` · ${m.name}` : ""}
                </span>
              </div>
              <div className="rounded-lg bg-white border border-slate-200 px-3 py-2 text-sm whitespace-pre-wrap break-words">
                {getContentText(m.content)}
                {m.tool_calls && Array.isArray(m.tool_calls) && m.tool_calls.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-slate-100 text-xs text-amber-700">
                    🔧 工具调用: {JSON.stringify(m.tool_calls, null, 2)}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
      {structuredResponse != null && (
        <div className="mt-4 p-3 rounded-lg bg-purple-50 border border-purple-200">
          <div className="text-xs font-semibold text-purple-700 mb-1">结构化响应</div>
          <pre className="text-xs font-mono text-purple-900 overflow-auto">
            {(() => {
              try {
                return JSON.stringify(structuredResponse, null, 2);
              } catch {
                return String(structuredResponse);
              }
            })()}
          </pre>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 6: 创建 `frontend/src/components/TraceListTable.tsx`**

```tsx
import { Link } from "react-router-dom";
import { Trash2, ChevronRight } from "lucide-react";
import type { Trace } from "@/types/trace";
import { useDeleteTrace } from "@/hooks/useTraces";

const STATUS_BADGE: Record<string, string> = {
  succeeded: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-amber-100 text-amber-700",
};

interface Props {
  traces: Trace[];
}

export default function TraceListTable({ traces }: Props) {
  const del = useDeleteTrace();
  return (
    <div className="overflow-hidden border border-slate-200 rounded-lg bg-white">
      <table className="w-full text-sm">
        <thead className="bg-slate-50 text-slate-600">
          <tr>
            <th className="text-left px-4 py-2 font-medium">名称</th>
            <th className="text-left px-4 py-2 font-medium">状态</th>
            <th className="text-left px-4 py-2 font-medium">事件数</th>
            <th className="text-left px-4 py-2 font-medium">耗时</th>
            <th className="text-left px-4 py-2 font-medium">开始时间</th>
            <th className="text-right px-4 py-2 font-medium">操作</th>
          </tr>
        </thead>
        <tbody>
          {traces.map((t) => (
            <tr key={t.trace_id} className="border-t border-slate-100 hover:bg-slate-50">
              <td className="px-4 py-2">
                <Link to={`/traces/${t.trace_id}`} className="text-blue-600 hover:underline font-medium">
                  {t.name ?? t.trace_id.slice(0, 8)}
                </Link>
              </td>
              <td className="px-4 py-2">
                <span className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[t.status]}`}>
                  {t.status}
                </span>
              </td>
              <td className="px-4 py-2 text-slate-600">{t.events.length}</td>
              <td className="px-4 py-2 text-slate-600">
                {t.duration_ms != null ? `${t.duration_ms} ms` : "-"}
              </td>
              <td className="px-4 py-2 text-slate-500 text-xs">
                {t.start_time ? new Date(t.start_time).toLocaleString("zh-CN", { hour12: false }) : "-"}
              </td>
              <td className="px-4 py-2 text-right">
                <div className="inline-flex gap-1">
                  <button
                    onClick={() => del.mutate(t.trace_id)}
                    className="p-1 text-slate-400 hover:text-red-600"
                    title="删除"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <Link to={`/traces/${t.trace_id}`} className="p-1 text-slate-400 hover:text-blue-600">
                    <ChevronRight className="w-4 h-4" />
                  </Link>
                </div>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 7: 创建 `frontend/src/components/TraceDetailHeader.tsx`**

```tsx
import type { Trace } from "@/types/trace";

const STATUS_BADGE: Record<string, string> = {
  succeeded: "bg-emerald-100 text-emerald-700",
  failed: "bg-red-100 text-red-700",
  running: "bg-amber-100 text-amber-700",
};

interface Props {
  trace: Trace;
}

export default function TraceDetailHeader({ trace }: Props) {
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-4">
      <div className="flex items-center gap-3 flex-wrap">
        <h1 className="text-xl font-semibold text-slate-900">
          {trace.name ?? trace.trace_id.slice(0, 8)}
        </h1>
        <span className={`text-xs px-2 py-0.5 rounded ${STATUS_BADGE[trace.status]}`}>
          {trace.status}
        </span>
        {trace.duration_ms != null && (
          <span className="text-sm text-slate-500">{trace.duration_ms} ms</span>
        )}
      </div>
      <div className="mt-2 text-xs text-slate-500 font-mono">
        {trace.trace_id}
      </div>
      {trace.start_time && (
        <div className="mt-1 text-xs text-slate-500">
          {new Date(trace.start_time).toLocaleString("zh-CN", { hour12: false })}
          {trace.end_time && ` → ${new Date(trace.end_time).toLocaleString("zh-CN", { hour12: false })}`}
        </div>
      )}
      {trace.error && (
        <div className="mt-2 p-2 rounded bg-red-50 border border-red-200 text-sm text-red-700">
          <span className="font-mono">{trace.error.type}:</span> {trace.error.message}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 8: 创建 `frontend/src/pages/TraceListPage.tsx`**

```tsx
import { useState } from "react";
import TraceListTable from "@/components/TraceListTable";
import { useTraces } from "@/hooks/useTraces";

export default function TraceListPage() {
  const [offset, setOffset] = useState(0);
  const limit = 20;
  const { data, isLoading, isError } = useTraces(limit, offset);

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-slate-900">Trace 日志</h1>
        <button
          onClick={() => setOffset(Math.max(0, offset - limit))}
          disabled={offset === 0}
          className="px-3 py-1 text-sm rounded border border-slate-300 disabled:opacity-40"
        >
          上一页
        </button>
      </div>
      {isLoading && <p className="text-slate-500">加载中...</p>}
      {isError && <p className="text-red-600">加载失败</p>}
      {data && <TraceListTable traces={data} />}
      {data && data.length === limit && (
        <div className="mt-4 text-center">
          <button
            onClick={() => setOffset(offset + limit)}
            className="px-3 py-1 text-sm rounded border border-slate-300"
          >
            下一页
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 9: 创建 `frontend/src/pages/TraceDetailPage.tsx`**

```tsx
import { useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft } from "lucide-react";
import TraceDetailHeader from "@/components/TraceDetailHeader";
import EventTimeline from "@/components/EventTimeline";
import CallTree from "@/components/CallTree";
import MessageFlow from "@/components/MessageFlow";
import JsonViewer from "@/components/JsonViewer";
import { useTrace } from "@/hooks/useTraces";

type Tab = "timeline" | "tree" | "messages" | "io";

export default function TraceDetailPage() {
  const { traceId } = useParams<{ traceId: string }>();
  const { data: trace, isLoading, isError } = useTrace(traceId!);
  const [tab, setTab] = useState<Tab>("tree");

  if (isLoading) return <p className="p-6 text-slate-500">加载中...</p>;
  if (isError || !trace) return <p className="p-6 text-red-600">未找到 trace</p>;

  const tabs: { key: Tab; label: string }[] = [
    { key: "tree", label: "调用树" },
    { key: "timeline", label: "时间线" },
    { key: "messages", label: "消息流" },
    { key: "io", label: "输入/输出" },
  ];

  return (
    <div className="max-w-6xl mx-auto p-6">
      <Link to="/" className="inline-flex items-center text-sm text-blue-600 hover:underline mb-3">
        <ArrowLeft className="w-4 h-4 mr-1" /> 返回列表
      </Link>
      <TraceDetailHeader trace={trace} />

      <div className="flex gap-2 mt-4 border-b border-slate-200">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
              tab === t.key
                ? "border-blue-500 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {tab === "tree" && <CallTree events={trace.events} />}
        {tab === "timeline" && <EventTimeline events={trace.events} />}
        {tab === "messages" && (
          <MessageFlow messages={trace.messages} structuredResponse={trace.structured_response} />
        )}
        {tab === "io" && (
          <div className="space-y-3">
            <JsonViewer data={trace.input} label="输入 (input)" defaultOpen />
            <JsonViewer data={trace.output} label="输出 (output)" defaultOpen />
            <JsonViewer data={trace.metadata} label="元数据 (metadata)" />
          </div>
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 10: 启动验证**

Run: `cd frontend && npm run dev`
Expected: 前端启动，列表页可访问（空状态）

- [ ] **Step 11: 提交**

```bash
git add frontend/src/components frontend/src/pages
git commit -m "feat(frontend): add trace list, detail, timeline, call tree and message flow"
```

---

### Task 11: 端到端联调验证

- [ ] **Step 1: 启动后端**

Run: `cd backend && uvicorn app.main:app --reload`

- [ ] **Step 2: 启动前端**

Run: `cd frontend && npm run dev`

- [ ] **Step 3: 用样例数据 POST 一个 trace**

用 curl 或 Swagger（http://localhost:8000/docs）POST `/api/v1/traces`，body 使用 `docs/plans` 中"核心数据模型"的 Trace 结构样例。

- [ ] **Step 4: 前端验证**

访问 http://localhost:5173，确认列表出现该 trace，点击进入详情，依次查看「调用树」「时间线」「消息流」「输入/输出」四个 tab。

- [ ] **Step 5: 提交**

```bash
git add -A
git commit -m "test: end-to-end verification with sample trace"
```

---

### Task 12: 文档

**Files:**
- Create: `docs/开发环境启动.md`
- Create: `docs/AI-Agent接入说明.md`
- Create: `README.md`

- [ ] **Step 1: 创建 `docs/开发环境启动.md`**

```markdown
# 开发环境启动

## 前置要求

- Python 3.11+
- Node.js 18+ / npm
- Git

## 后端

\`\`\`bash
cd backend
python -m venv .venv
.venv\\Scripts\\activate          # Windows
# source .venv/bin/activate      # macOS/Linux
pip install -e ".[dev]"

# 默认内存存储；如需文件存储，复制 .env.example 为 .env 并修改
# TRACE_STORAGE_BACKEND=file
# TRACE_FILE_STORAGE_DIR=./data/traces

uvicorn app.main:app --reload
\`\`\`

后端启动在 http://localhost:8000 ，Swagger 文档 http://localhost:8000/docs

## 前端

\`\`\`bash
cd frontend
npm install
npm run dev
\`\`\`

前端启动在 http://localhost:5173 ，已配置 `/api` 代理到后端。

## 验证

1. 后端、前端都启动后，访问 http://localhost:5173
2. 通过 Swagger POST 一个 trace，或运行 AI Agent 接入示例（见 AI-Agent接入说明.md）
3. 在前端列表页查看，点击详情查看调用树/时间线/消息流
```

- [ ] **Step 2: 创建 `docs/AI-Agent接入说明.md`**

```markdown
# AI Agent 接入说明

本系统通过一个轻量 callback 包采集 LangChain 调用轨迹并推送到后端。

## 1. 安装 callback 包

在 AI Agent 项目中安装 `langchain-trace-cb`：

\`\`\`bash
# 从本仓库安装（开发模式）
pip install -e ./client

# 或打包后安装
pip install langchain-trace-cb
\`\`\`

## 2. 使用方式

\`\`\`python
from langchain_trace_cb import TraceCallbackHandler

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
    config={"callbacks": [trace_handler]},
)
\`\`\`

callback 会在 invoke 执行期间采集所有事件（LLM/Chain/Tool/Agent 等），在根 chain 结束时一次性 POST 到后端。

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

\`\`\`python
TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",  # 后端地址
    name="my-agent",                                  # trace 名称
    tags=["prod"],                                    # 标签列表
    metadata={"key": "value"},                        # 元数据
    client=TraceClient(timeout=5.0),                  # 可选：自定义客户端
)
\`\`\`

## 5. 错误处理

callback 推送失败**不会**抛异常影响 agent 执行，仅记录 warning 日志。
如需感知推送失败，可在 `TraceClient` 上自定义重试或回调。

## 6. 完整示例（基于 create_react_agent）

\`\`\`python
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
from langchain_trace_cb import TraceCallbackHandler

def get_weather(city: str) -> str:
    \"\"\"获取指定城市天气。\"\"\"
    return f"{city} 今天晴朗，25 度。"

model = ChatOpenAI(model="qwen-flash", base_url="...")
agent = create_react_agent(model=model, tools=[get_weather])

handler = TraceCallbackHandler(
    endpoint="http://localhost:8000/api/v1/traces",
    name="weather-agent",
)

result = agent.invoke(
    {"messages": [{"role": "user", "content": "广州今天天气如何？"}]},
    config={"callbacks": [handler]},
)

print(result["structured_response"])
\`\`\`

执行后，在 http://localhost:5173 即可查看本次调用的完整轨迹。

## 7. 存储扩展

后端默认使用内存存储（重启丢失）。如需持久化：

\`\`\`bash
# backend/.env
TRACE_STORAGE_BACKEND=file
TRACE_FILE_STORAGE_DIR=./data/traces
\`\`\`

如需扩展数据库存储，继承 `app.repositories.base.TraceRepository` 并在 `dependencies.py` 中注册。
```

- [ ] **Step 3: 创建 `README.md`**

```markdown
# LangChain Trace Logger

记录与可视化 LangChain 调用轨迹的日志系统。

## 架构

- **后端** (`backend/`): FastAPI + 仓储模式（内存/文件/可扩展）
- **Callback 客户端** (`client/`): 轻量 LangChain callback，HTTP 推送 trace
- **前端** (`frontend/`): React + Vite + TailwindCSS，列表 + 详情（调用树/时间线/消息流）

## 快速开始

见 [开发环境启动](docs/开发环境启动.md)

## AI Agent 接入

见 [AI-Agent 接入说明](docs/AI-Agent接入说明.md)

## 技术栈

- Python 3.11+, FastAPI, Pydantic v2, Uvicorn
- React 18, Vite, TypeScript, TailwindCSS, TanStack Query
- langchain-core v0.3+ (兼容 langchain v1.3.11)
```

- [ ] **Step 4: 提交**

```bash
git add docs/ README.md
git commit -m "docs: add startup guide and AI agent integration guide"
```

---

## 四、自检清单

- [x] **架构决策**: HTTP API 推送，附对比说明
- [x] **数据模型**: Trace + Event，含 run_id/parent_run_id 构建树
- [x] **存储扩展**: TraceRepository ABC + 内存/文件两实现，可在 dependencies.py 切换
- [x] **Callback**: 覆盖 LLM/Chat/Chain/Tool/Agent/Retriever/Text 全部事件
- [x] **API**: create/list/get/delete/count
- [x] **前端**: 列表 + 详情四视图（调用树/时间线/消息流/IO）
- [x] **文档**: 启动文档 + 接入说明 + README
- [x] **测试**: 模型/仓储/服务/API/Callback 均有测试
```
