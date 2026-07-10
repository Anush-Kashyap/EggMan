from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional, List

@dataclass(slots=True)
class PromptContext:
    """Carries request-specific data required by various prompt modules."""

    user_message: str = ""
    mode: str = "casual"  # "casual", "teaching", "programming"
    is_voice: bool = False
    persona_prompt: Optional[str] = None
    has_image: bool = False
    has_tools: bool = False
    has_scheduler: bool = False
    developer_mode: bool = False
    retrieved_memories: List[Any] = field(default_factory=list)
    retrieved_knowledge: List[str] = field(default_factory=list)
