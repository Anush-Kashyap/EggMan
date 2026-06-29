from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from backend.memory.memory_types import MemoryEntry


@dataclass(slots=True)
class MessageEntry:
    sender: str
    text: str
    timestamp: Optional[str] = None


@dataclass(slots=True)
class Attachment:
    content_id: Optional[str] = None
    filename: Optional[str] = None
    content_type: Optional[str] = None
    uri: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ToolRequest:
    name: str
    args: Dict[str, Any] = field(default_factory=dict)
    description: Optional[str] = None


@dataclass(slots=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


@dataclass(slots=True)
class AIRequest:
    system_prompt: str = "You are EggMan, a friendly desktop companion."
    user_message: str = ""
    conversation_history: List[MessageEntry] = field(default_factory=list)
    memories: List[MemoryEntry] = field(default_factory=list)
    tool_results: List[Dict[str, Any]] = field(default_factory=list)
    attachments: List[Attachment] = field(default_factory=list)
    images: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    model_name: Optional[str] = None


@dataclass(slots=True)
class AIResponse:
    response_text: str = ""
    model_name: Optional[str] = None
    finish_reason: Optional[str] = None
    token_usage: Optional[TokenUsage] = None
    tool_requests: List[ToolRequest] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None
    provider_name: Optional[str] = None

    @property
    def successful(self) -> bool:
        return self.error is None and bool(self.response_text)
