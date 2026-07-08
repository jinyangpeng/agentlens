"""终端日志回调处理器。

在 LangChain 调用过程中实时打印结构化日志，包括 chain/llm/tool 的开始、结束、耗时、
token 用量等。通过 ``logging`` 模块输出，可被标准日志体系接管。

用法::

    from agentlens_cb import LoggerCallbackHandler

    handler = LoggerCallbackHandler()
    result = agent.invoke({...}, config={"callbacks": [handler]})

也可通过 ``TraceCallbackHandler(verbose=True)`` 自动启用，无需单独传入。
"""
import json
import logging
import time
from typing import Any
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger("agentlens.verbose")

# 默认日志格式（可被调用方覆盖）
_DEFAULT_FORMAT = "%(asctime)s | %(levelname)-5s | %(message)s"
logging.basicConfig(format=_DEFAULT_FORMAT, level=logging.INFO)


def _safe(obj: Any) -> Any:
    """与 callback.py 保持一致的序列化逻辑。"""
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


def _truncate(text: str, limit: int = 500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "..."


class LoggerCallbackHandler(BaseCallbackHandler):
    """结构化终端日志处理器。

    与 ``TraceCallbackHandler`` 不同，本类仅做终端打印，不推送 trace。
    两者可同时使用（通过 ``TraceCallbackHandler(verbose=True)`` 自动组合）。
    """

    def __init__(self, level: int = logging.INFO) -> None:
        self._level = level
        self._token_usage = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }
        self._chain_times: dict[str, float] = {}
        self._llm_times: dict[str, float] = {}
        self._tool_times: dict[str, float] = {}
        # 嵌套深度：通过 parent_run_id 链推算
        self._depth_map: dict[str, int] = {}  # run_id -> depth

    # ---- 辅助 ----

    def _log(self, msg: str, level: int | None = None) -> None:
        logger.log(level or self._level, msg)

    def _depth(self, run_id: str, parent_run_id: str | None) -> int:
        depth = 0 if parent_run_id is None else self._depth_map.get(parent_run_id, 0) + 1
        self._depth_map[run_id] = depth
        return depth

    def _indent(self, depth: int) -> str:
        return "  " * depth

    def _serialize(self, obj: Any) -> str:
        safe = _safe(obj)
        try:
            return _truncate(json.dumps(safe, ensure_ascii=False, indent=2, default=str))
        except Exception:
            return _truncate(str(safe))

    def _format_usage(self, usage: dict) -> str:
        return (
            f"prompt={usage.get('prompt_tokens', 0)}, "
            f"completion={usage.get('completion_tokens', 0)}, "
            f"total={usage.get('total_tokens', 0)}"
        )

    # ---- Chain ----

    def on_chain_start(
        self, serialized: dict, inputs: dict, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        pid = str(parent_run_id) if parent_run_id else None
        depth = self._depth(rid, pid)
        self._chain_times[rid] = time.perf_counter()
        name = (serialized or {}).get("name") or "chain"
        self._log(f"{self._indent(depth)}[CHAIN START] {name} (depth={depth})")
        if inputs:
            self._log(f"{self._indent(depth)}  input:\n{self._serialize(inputs)}")

    def on_chain_end(
        self, outputs: dict, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        depth = self._depth_map.get(rid, 0)
        elapsed = time.perf_counter() - self._chain_times.pop(rid, time.perf_counter())
        self._log(f"{self._indent(depth)}[CHAIN END]   ({elapsed:.3f}s)")
        if outputs:
            self._log(f"{self._indent(depth)}  output:\n{self._serialize(outputs)}")

    def on_chain_error(
        self, error: BaseException, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        depth = self._depth_map.get(rid, 0)
        self._log(
            f"{self._indent(depth)}[CHAIN ERROR] {type(error).__name__}: {error}",
            level=logging.ERROR,
        )

    # ---- LLM ----

    def on_llm_start(
        self, serialized: dict, prompts: list[str], *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        self._llm_times[rid] = time.perf_counter()
        name = (serialized or {}).get("name") or "llm"
        self._log(f"  [LLM START] {name}")
        if prompts:
            self._log(f"  [LLM START]   prompt:\n{_truncate(str(prompts[0]))}")

    def on_chat_model_start(
        self, serialized: dict, messages: list[list[Any]], *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        self._llm_times[rid] = time.perf_counter()
        name = (serialized or {}).get("name") or "chat_model"
        self._log(f"  [LLM START] {name}")
        if messages and messages[0]:
            self._log(f"  [LLM START]   messages:\n{self._serialize(messages[0])}")

    def on_llm_end(
        self, response: LLMResult, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        elapsed = time.perf_counter() - self._llm_times.pop(rid, time.perf_counter())
        self._log(f"  [LLM END]   ({elapsed:.3f}s)")

        # 响应预览
        if response.generations and response.generations[0]:
            gen = response.generations[0][0]
            if gen.message.tool_calls:
                tcs = [f"{tc['name']}({json.dumps(tc['args'], ensure_ascii=False)})" for tc in gen.message.tool_calls]
                self._log(f"  [LLM END]   tool_calls: {', '.join(tcs)}")
            elif gen.text:
                self._log(f"  [LLM END]   response: {_truncate(gen.text)}")

        # token 用量
        usage = {}
        if response.llm_output:
            usage = response.llm_output.get("token_usage") or response.llm_output.get("usage", {})
        if usage:
            self._log(f"  [LLM END]   tokens: {self._format_usage(usage)}")
            self._token_usage["prompt_tokens"] += usage.get("prompt_tokens", 0)
            self._token_usage["completion_tokens"] += usage.get("completion_tokens", 0)
            self._token_usage["total_tokens"] += usage.get("total_tokens", 0)
            self._log(
                f"  [LLM END]   cumulative: {self._format_usage(self._token_usage)}"
            )

    def on_llm_error(
        self, error: BaseException, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        self._log(f"  [LLM ERROR] {type(error).__name__}: {error}", level=logging.ERROR)

    # ---- Tool ----

    def on_tool_start(
        self, serialized: dict, input_str: str, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        self._tool_times[rid] = time.perf_counter()
        name = (serialized or {}).get("name") or "tool"
        self._log(f"  [TOOL START] {name}: {_truncate(input_str)}")

    def on_tool_end(
        self, output: str, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        rid = str(run_id)
        elapsed = time.perf_counter() - self._tool_times.pop(rid, time.perf_counter())
        self._log(f"  [TOOL END]   ({elapsed:.3f}s) {_truncate(str(output))}")

    def on_tool_error(
        self, error: BaseException, *, run_id: UUID,
        parent_run_id: UUID | None = None, **kwargs: Any,
    ) -> Any:
        self._log(f"  [TOOL ERROR] {type(error).__name__}: {error}", level=logging.ERROR)

    # ---- 最终汇总 ----

    def on_chain_end_root(self) -> None:
        """根 chain 结束时打印 token 汇总。"""
        if self._token_usage["total_tokens"] > 0:
            self._log(
                f"[SUMMARY] total tokens: {self._format_usage(self._token_usage)}"
            )
