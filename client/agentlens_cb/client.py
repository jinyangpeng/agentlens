"""HTTP 客户端，将 trace 推送到后端。

设计要点（降级）：
- send 在后台线程执行，调用方立即返回，绝不阻塞 agent 主流程
- 后端不可达时仅记录 warning，不抛异常
- timeout 缩短到 2s，避免长时间挂起
- 首次连接失败后进入「熔断」状态，短期内跳过发送（默认 30s）
- 线程默认 non-daemon + 主进程退出前短暂 join，确保同步脚本退出前推送完成
"""
import atexit
import logging
import threading
import time
from typing import Any

import httpx

from agentlens_cb.models import TracePayload

logger = logging.getLogger(__name__)

# 全局待 join 的线程集合
_pending_threads: list[threading.Thread] = []
_pending_lock = threading.Lock()


def _wait_pending(timeout: float = 3.0) -> None:
    """进程退出前等待所有挂起的推送完成（最多 timeout 秒）。"""
    with _pending_lock:
        threads = list(_pending_threads)
        _pending_threads.clear()
    for t in threads:
        t.join(timeout=timeout)


atexit.register(_wait_pending)


class TraceClient:
    """向后端推送 trace 的 HTTP 客户端（异步、可降级）。"""

    def __init__(
        self,
        endpoint: str = "http://localhost:8000/api/v1/traces",
        timeout: float = 2.0,
        headers: dict[str, str] | None = None,
        # 熔断：连续失败后跳过发送的冷却时间（秒）。0 表示不熔断。
        circuit_break_seconds: float = 30.0,
    ) -> None:
        self._endpoint = endpoint
        self._timeout = timeout
        self._headers = headers or {}
        self._break_seconds = circuit_break_seconds
        self._lock = threading.Lock()
        self._last_fail_ts: float = 0.0
        self._closed = False

    def send(self, payload: TracePayload) -> None:
        """异步发送 trace。立即返回，不阻塞调用方，不抛异常。"""
        if self._closed:
            return
        # 熔断检查：连续失败后短期内跳过
        if self._break_seconds > 0 and self._is_in_cooldown():
            return
        # non-daemon 线程 + 注册到全局待 join 列表，
        # 确保同步脚本（python script.py）退出前推送能完成
        t = threading.Thread(target=self._send_sync, args=(payload,), daemon=False)
        with _pending_lock:
            _pending_threads.append(t)
        t.start()

    def _is_in_cooldown(self) -> bool:
        with self._lock:
            if self._last_fail_ts <= 0:
                return False
            return (time.monotonic() - self._last_fail_ts) < self._break_seconds

    def _send_sync(self, payload: TracePayload) -> None:
        """实际同步发送（在后台线程执行）。"""
        try:
            resp = httpx.post(
                self._endpoint,
                content=payload.model_dump_json(),
                headers={"Content-Type": "application/json", **self._headers},
                timeout=self._timeout,
            )
            resp.raise_for_status()
            # 成功：清空熔断状态
            with self._lock:
                self._last_fail_ts = 0.0
        except Exception as e:
            # 失败：记录时间，触发熔断冷却
            with self._lock:
                self._last_fail_ts = time.monotonic()
            logger.warning(
                "Trace 推送失败（agent 不受影响，已降级）: %s", e
            )
        finally:
            # 完成后从待 join 列表移除
            current = threading.current_thread()
            with _pending_lock:
                if current in _pending_threads:
                    _pending_threads.remove(current)

    def close(self) -> None:
        """标记关闭，停止后续发送。"""
        self._closed = True
