"""AgentLens 统一入口。

整合 trace 推送、终端日志、手动 trace 上下文和装饰器，提供四种接入方式：

1. **LangChain callback**（最常用）::

       lens = AgentLens(endpoint="http://localhost:8000/api/v1/traces", verbose=True)
       result = agent.invoke({...}, config={"callbacks": [lens.trace_handler()]})

2. **装饰器**（自动追踪函数执行，不依赖 LangChain callback）::

       lens = AgentLens(endpoint="...")

       @lens.observe
       def my_agent(query: str) -> str:
           return agent.invoke({"messages": [...]})

3. **上下文管理器**（手动控制 trace 生命周期）::

       with lens.trace("my_agent") as ctx:
           ctx.event("chain_start", inputs={"query": "hello"})
           result = do_something()
           ctx.event("chain_end", outputs=result)

4. **手动推送**（完全自主，适配任何 AI 框架）::

       lens.push(
           name="custom_agent",
           input={"query": "hello"},
           output={"answer": "hi"},
           events=[EventPayload(...)],
       )

所有方式复用同一 ``TraceClient``（连接复用 + 熔断降级），数据格式与后端 ``POST /api/v1/traces`` 对齐。
"""
import functools
import logging
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Generator
from uuid import uuid4

from agentlens_cb.client import TraceClient
from agentlens_cb.models import EventPayload, TracePayload

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TraceContext:
    """手动 trace 上下文。

    由 ``AgentLens.trace()`` 创建，允许调用方在执行过程中逐步添加事件，
    退出 ``with`` 块时自动推送 trace。异常退出时自动标记为 failed。
    """

    def __init__(
        self,
        client: TraceClient,
        name: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> None:
        self._client = client
        self._name = name
        self._tags = tags or []
        self._metadata = metadata or {}
        self._thread_id = thread_id
        self._events: list[EventPayload] = []
        self._start_time = _now_iso()
        self._failed = False
        self._error: dict[str, Any] | None = None
        self._root_run_id = str(uuid4())
        self._completed = False

    def event(
        self,
        event_type: str,
        run_id: str | None = None,
        parent_run_id: str | None = None,
        name: str | None = None,
        inputs: Any | None = None,
        outputs: Any | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        level: str = "info",
        is_middleware: bool = False,
        middleware_name: str | None = None,
        node_name: str | None = None,
    ) -> EventPayload:
        """添加一个事件到当前 trace。"""
        ev = EventPayload(
            run_id=run_id or self._root_run_id,
            parent_run_id=parent_run_id,
            event_type=event_type,
            name=name,
            inputs=inputs,
            outputs=outputs,
            metadata=metadata or {},
            tags=tags or [],
            level=level,
            is_middleware=is_middleware,
            middleware_name=middleware_name,
            node_name=node_name,
        )
        self._events.append(ev)
        return ev

    def complete(
        self,
        output: Any = None,
        messages: list[Any] | None = None,
    ) -> None:
        """正常完成 trace 并推送。"""
        if self._completed:
            return
        self._completed = True
        payload = TracePayload(
            name=self._name,
            thread_id=self._thread_id,
            output=output,
            messages=messages or [],
            metadata=self._metadata,
            tags=self._tags,
            start_time=self._start_time,
            end_time=_now_iso(),
            status="succeeded",
            events=self._events,
        )
        self._client.send(payload)

    def fail(self, error: Exception) -> None:
        """异常完成 trace 并推送。"""
        if self._completed:
            return
        self._completed = True
        self._failed = True
        self._error = {"type": type(error).__name__, "message": str(error)}
        payload = TracePayload(
            name=self._name,
            thread_id=self._thread_id,
            metadata=self._metadata,
            tags=self._tags,
            start_time=self._start_time,
            end_time=_now_iso(),
            status="failed",
            error=self._error,
            events=self._events,
        )
        self._client.send(payload)


class AgentLens:
    """统一入口：整合 trace 推送、终端日志、装饰器和上下文管理器。

    所有方式共享同一个 ``TraceClient``（连接复用 + 熔断降级）。
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/traces",
        verbose: bool = False,
        timeout: float = 2.0,
        headers: dict[str, str] | None = None,
        circuit_break_seconds: float = 30.0,
    ) -> None:
        self._client = TraceClient(
            endpoint=endpoint,
            timeout=timeout,
            headers=headers,
            circuit_break_seconds=circuit_break_seconds,
        )
        self._verbose = verbose

    # ---- 方式1：LangChain callback ----

    def trace_handler(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        verbose: bool | None = None,
    ) -> "TraceCallbackHandler":
        """返回配置好的 ``TraceCallbackHandler``，直接传入 LangChain callbacks。"""
        from agentlens_cb.callback import TraceCallbackHandler
        return TraceCallbackHandler(
            client=self._client,
            name=name,
            tags=tags,
            metadata=metadata,
            verbose=self._verbose if verbose is None else verbose,
        )

    # ---- 方式2：装饰器 ----

    def observe(
        self,
        func: Any | None = None,
        *,
        name: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Any:
        """装饰器：自动追踪函数执行，不依赖 LangChain callback 机制。

        用法::

            @lens.observe
            def my_agent(query):
                return agent.invoke({"messages": [...]})

            @lens.observe(name="custom", tags=["production"])
            def another_agent(query):
                ...
        """

        def decorator(f: Any) -> Any:
            @functools.wraps(f)
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                trace_name = name or f.__name__
                with self.trace(trace_name, tags=tags, metadata=metadata) as ctx:
                    try:
                        result = f(*args, **kwargs)
                        ctx.complete(output=result)
                        return result
                    except Exception as e:
                        ctx.fail(e)
                        raise

            return wrapper

        if func is not None:
            return decorator(func)
        return decorator

    # ---- 方式3：上下文管理器 ----

    @contextmanager
    def trace(
        self,
        name: str | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        thread_id: str | None = None,
    ) -> Generator[TraceContext, None, None]:
        """上下文管理器：手动管理 trace 生命周期。

        用法::

            with lens.trace("my_agent") as ctx:
                ctx.event("chain_start", inputs={"query": "hello"})
                result = do_something()
                ctx.event("chain_end", outputs=result)
            # 退出 with 块时自动推送 trace
        """
        ctx = TraceContext(
            client=self._client,
            name=name,
            tags=tags,
            metadata=metadata,
            thread_id=thread_id,
        )
        try:
            yield ctx
        except Exception as e:
            ctx.fail(e)
            raise
        else:
            if not ctx._completed:
                ctx.complete()

    # ---- 方式4：手动推送 ----

    def push(
        self,
        name: str | None = None,
        input: Any | None = None,
        output: Any | None = None,
        messages: list[Any] | None = None,
        structured_response: Any | None = None,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        thread_id: str | None = None,
        events: list[EventPayload] | None = None,
        status: str = "succeeded",
        error: dict[str, Any] | None = None,
    ) -> None:
        """手动推送 trace（完全自主控制，适配任何 AI 框架）。

        用法::

            lens.push(
                name="custom_agent",
                input={"query": "hello"},
                output={"answer": "hi"},
                events=[EventPayload(run_id="r1", event_type="chain_start", ...)],
            )
        """
        now = _now_iso()
        payload = TracePayload(
            name=name,
            thread_id=thread_id,
            input=input,
            output=output,
            messages=messages or [],
            structured_response=structured_response,
            metadata=metadata or {},
            tags=tags or [],
            start_time=now,
            end_time=now,
            status=status,
            error=error,
            events=events or [],
        )
        self._client.send(payload)
