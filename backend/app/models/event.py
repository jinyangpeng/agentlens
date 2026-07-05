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
    # Middleware 识别（client 端启发式填充，向后兼容旧数据）
    is_middleware: bool = False
    middleware_name: str | None = None
    node_name: str | None = None  # LangGraph node 名（来自 metadata.langgraph_node）
