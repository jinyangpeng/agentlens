"""LangChain BaseCallbackHandler 实现：采集事件并推送 trace。"""
import logging
from typing import Any
from uuid import UUID

from langchain_core.agents import AgentAction, AgentFinish
from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.messages import BaseMessage
from langchain_core.outputs import LLMResult

from agentlens_cb.client import TraceClient
from agentlens_cb.logger_handler import LoggerCallbackHandler
from agentlens_cb.middleware_registry import detect_middleware_type
from agentlens_cb.models import EventPayload, TracePayload

logger = logging.getLogger(__name__)


def _resolve_mw_name(class_candidate: str | None) -> tuple[str | None, str | None]:
    """将候选类名解析为 (标准类名, lc_source)。

    若匹配到内置注册表，则返回标准类名与对应 lc_source；
    否则原样返回候选名，lc_source 为 None（自定义 middleware）。
    """
    if not class_candidate:
        return None, None
    meta = detect_middleware_type(class_candidate)
    if meta:
        return meta.class_name, meta.lc_source
    return class_candidate, None


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
        verbose: bool = False,
    ) -> None:
        self._client = client or TraceClient(endpoint=endpoint)
        self._name = name
        self._tags = tags or []
        self._metadata = metadata or {}
        self._events: list[EventPayload] = []
        # 缓存 run_id -> (is_middleware, middleware_name, node_name, lc_source)，
        # 供同 run 的 chain_end / chain_error / llm_end 等事件回填 middleware 元数据。
        self._run_mw_cache: dict[str, tuple[bool, str | None, str | None, str | None]] = {}
        self._root_run_id: str | None = None
        self._root_name: str | None = name
        self._root_inputs: Any | None = None
        self._thread_id: str | None = None
        self._failed = False
        self._error: dict[str, Any] | None = None
        # 终端日志开关：verbose=True 时实时打印调用链
        self._verbose = verbose
        self._logger_handler: LoggerCallbackHandler | None = (
            LoggerCallbackHandler() if verbose else None
        )

    # ---- 内部辅助 ----
    def _add(self, event: EventPayload) -> None:
        self._events.append(event)
        if self._root_run_id is None:
            self._root_run_id = event.run_id

    def _delegate(self, method: str, *args: Any, **kwargs: Any) -> None:
        """委托到 LoggerCallbackHandler（verbose 模式下）。日志异常不影响主流程。"""
        if self._logger_handler:
            try:
                getattr(self._logger_handler, method)(*args, **kwargs)
            except Exception:
                pass

    def _lookup_mw(self, run_id: str) -> tuple[bool, str | None, str | None, str | None]:
        """从缓存查 run_id 的 middleware 元数据；非 chain 事件用它回填。"""
        return self._run_mw_cache.get(
            run_id, (False, None, None, None)
        )

    def _rid(self, run_id: UUID) -> str:
        return str(run_id)

    def _pid(self, parent_run_id: UUID | None) -> str | None:
        return str(parent_run_id) if parent_run_id else None

    def _ser_name(self, serialized: dict | None) -> str | None:
        if not serialized:
            return None
        return serialized.get("name") or serialized.get("id", [None])[-1]

    @staticmethod
    def _extract_thread_id(metadata: dict | None) -> str | None:
        """从 LangChain callback metadata 提取 thread_id。

        LangGraph 会把 config={"configurable": {"thread_id": "xxx"}} 注入到
        每个回调事件的 metadata 参数里。同时兜底几种常见位置。
        """
        if not metadata:
            return None
        # 1. LangGraph 标准：metadata.configurable.thread_id
        conf = metadata.get("configurable") or {}
        tid = conf.get("thread_id")
        # 2. 兜底：metadata 顶层 thread_id
        if not tid:
            tid = metadata.get("thread_id")
        # 3. 兜底：metadata.configurable.checkpoint_id（部分 LangGraph 版本）
        if not tid:
            tid = conf.get("checkpoint_id")
        if tid:
            tid = str(tid)
            logger.debug("TraceCallbackHandler 提取到 thread_id=%s", tid)
        else:
            logger.debug("TraceCallbackHandler 未在 metadata 中找到 thread_id，keys=%s", list(metadata.keys()))
        return tid

    @staticmethod
    def _detect_middleware(
        serialized: dict | None,
        name: str | None,
        metadata: dict | None,
        tags: list[str] | None,
    ) -> tuple[bool, str | None, str | None, str | None]:
        """启发式判断 callback event 是否由 LangChain v1 AgentMiddleware 触发。

        Returns: (is_middleware, middleware_name, node_name, lc_source)

        启发式策略（按优先级）：
        1. 显式 tag：tags 含 ``langchain:middleware`` 前缀
        2. 类名后缀：class 名以 ``Middleware`` 结尾
        3. LangGraph node 兜底：node_name 存在且非 agent/tools/model 核心 node，且首字母大写

        检测到 middleware 后，会通过 ``middleware_registry.detect_middleware_type``
        将类名标准化为内置 middleware 的标准类名，并填充 ``lc_source``。
        未匹配到内置注册表的自定义 middleware 仍按原候选名返回，``lc_source=None``。
        """
        # 提取 node_name
        node_name: str | None = None
        if isinstance(metadata, dict):
            ln = metadata.get("langgraph_node")
            if isinstance(ln, str) and ln:
                node_name = ln

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
            mw_name, lc_source = _resolve_mw_name(class_candidate)
            return True, mw_name, node_name, lc_source

        # 启发式 2: 类名以 Middleware 结尾
        if class_candidate and class_candidate.endswith("Middleware"):
            mw_name, lc_source = _resolve_mw_name(class_candidate)
            return True, mw_name, node_name, lc_source

        # 启发式 3: node_name 是首字母大写的非核心 node
        if (
            node_name
            and node_name not in {"agent", "tools", "model"}
            and node_name[0].isupper()
            and node_name not in {"_write", "__start__", "__end__"}
        ):
            mw_name, lc_source = _resolve_mw_name(class_candidate)
            return True, mw_name, node_name, lc_source

        return False, None, node_name, None

    # ---- LLM / Chat ----
    def on_llm_start(
        self, serialized: dict, prompts: list[str], *, run_id: UUID,
        parent_run_id: UUID | None = None, tags: list[str] | None = None,
        metadata: dict | None = None, **kwargs: Any,
    ) -> Any:
        self._delegate("on_llm_start", serialized, prompts, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)
        is_mw, mw_name, node, lc_source = self._detect_middleware(serialized, self._ser_name(serialized), metadata, tags)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="llm_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"prompts": prompts},
            tags=tags or [], metadata=metadata or {},
            is_middleware=is_mw, middleware_name=mw_name, node_name=node,
            lc_source=lc_source,
        ))

    def on_chat_model_start(
        self, serialized: dict, messages: list[list[BaseMessage]], *, run_id: UUID,
        parent_run_id: UUID | None = None, tags: list[str] | None = None,
        metadata: dict | None = None, **kwargs: Any,
    ) -> Any:
        self._delegate("on_chat_model_start", serialized, messages, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)
        is_mw, mw_name, node, lc_source = self._detect_middleware(serialized, self._ser_name(serialized), metadata, tags)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="llm_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"messages": _safe(messages)},
            tags=tags or [], metadata=metadata or {},
            is_middleware=is_mw, middleware_name=mw_name, node_name=node,
            lc_source=lc_source,
        ))

    def on_llm_end(self, response: LLMResult, *, run_id: UUID,
                   parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._delegate("on_llm_end", response, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="llm_end", outputs=_safe(response),
        ))

    def on_llm_error(self, error: BaseException, *, run_id: UUID,
                     parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._delegate("on_llm_error", error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
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
        self._delegate("on_chain_start", serialized, inputs, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)
        name = self._ser_name(serialized)
        is_mw, mw_name, node, lc_source = self._detect_middleware(serialized, name, metadata, tags)
        # 缓存以供同 run 的 chain_end / llm_end 等回填
        self._run_mw_cache[str(run_id)] = (is_mw, mw_name, node, lc_source)
        if self._root_run_id is None:
            self._root_run_id = str(run_id)
            self._root_name = name
            self._root_inputs = _safe(inputs)
            # 根 chain 首次出现时提取 thread_id
            self._thread_id = self._extract_thread_id(metadata)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chain_start", name=name, serialized=serialized,
            inputs=_safe(inputs), tags=tags or [], metadata=metadata or {},
            is_middleware=is_mw, middleware_name=mw_name, node_name=node,
            lc_source=lc_source,
        ))

    def on_chain_end(self, outputs: dict, *, run_id: UUID,
                     parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._delegate("on_chain_end", outputs, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
        is_mw, mw_name, node, lc_source = self._lookup_mw(str(run_id))
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chain_end", outputs=_safe(outputs),
            is_middleware=is_mw, middleware_name=mw_name, node_name=node,
            lc_source=lc_source,
        ))
        if run_id is not None and str(run_id) == self._root_run_id:
            self._finalize(output=_safe(outputs), outputs_dict=outputs)

    def on_chain_error(self, error: BaseException, *, run_id: UUID,
                       parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._delegate("on_chain_error", error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
        self._failed = True
        self._error = {"type": type(error).__name__, "message": str(error)}
        is_mw, mw_name, node, lc_source = self._lookup_mw(str(run_id))
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="chain_error", outputs=_safe(error), level="error",
            is_middleware=is_mw, middleware_name=mw_name, node_name=node,
            lc_source=lc_source,
        ))

    # ---- Tool ----
    def on_tool_start(self, serialized: dict, input_str: str, *, run_id: UUID,
                      parent_run_id: UUID | None = None, tags: list[str] | None = None,
                      metadata: dict | None = None, **kwargs: Any) -> Any:
        self._delegate("on_tool_start", serialized, input_str, run_id=run_id, parent_run_id=parent_run_id, tags=tags, metadata=metadata, **kwargs)
        is_mw, mw_name, node, lc_source = self._detect_middleware(serialized, self._ser_name(serialized), metadata, tags)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="tool_start", name=self._ser_name(serialized),
            serialized=serialized, inputs={"input": input_str},
            tags=tags or [], metadata=metadata or {},
            is_middleware=is_mw, middleware_name=mw_name, node_name=node,
            lc_source=lc_source,
        ))

    def on_tool_end(self, output: str, *, run_id: UUID,
                    parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._delegate("on_tool_end", output, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
        self._add(EventPayload(
            run_id=self._rid(run_id), parent_run_id=self._pid(parent_run_id),
            event_type="tool_end", outputs=_safe(output),
        ))

    def on_tool_error(self, error: BaseException, *, run_id: UUID,
                      parent_run_id: UUID | None = None, **kwargs: Any) -> Any:
        self._delegate("on_tool_error", error, run_id=run_id, parent_run_id=parent_run_id, **kwargs)
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
            name=self._name or self._root_name,
            thread_id=self._thread_id,
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
        # verbose 模式：打印 token 汇总
        if self._logger_handler:
            self._logger_handler.on_chain_end_root()
        # 重置以支持 handler 复用
        self._events = []
        self._root_run_id = None
        self._root_name = None
        self._root_inputs = None
        self._thread_id = None
        self._failed = False
        self._error = None
