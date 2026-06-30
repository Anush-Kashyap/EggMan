from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any, List

from backend.memory.models import MemoryRecord
from backend.retrieval.retrieval_service import RetrievalService


@dataclass(slots=True)
class ContextPayload:
    """Structured context object prepared for downstream prompt formatting."""

    system_prompt: str = "You are EggMan, a friendly desktop companion."
    recent_conversation: List[tuple[str, str]] = field(default_factory=list)
    retrieved_memories: List[Any] = field(default_factory=list)
    current_user_message: str = ""


class ContextBuilder:
    """Builds a structured context object without talking to any AI provider directly."""

    def __init__(self, retrieval_service: RetrievalService | None = None, knowledge_manager: Any = None) -> None:
        self._retrieval_service = retrieval_service
        self._knowledge_manager = knowledge_manager
        self._logger = logging.getLogger("eggman")

    def build_context(
        self,
        user_message: str,
        recent_conversation: List[tuple[str, str]] | None = None,
        memories: List[Any] | None = None,
        system_prompt: str | None = None,
    ) -> ContextPayload:
        retrieved_memories = memories or []
        if self._retrieval_service is not None:
            retrieved_memories = self._retrieval_service.retrieve(user_message)
        base_prompt = system_prompt or "You are EggMan, a friendly desktop companion."
        prompt_with_memories = self._inject_memories(base_prompt, retrieved_memories)

        # Inject KB document context if available
        if self._knowledge_manager is not None:
            kb_contexts = self._knowledge_manager.search(user_message)
            if kb_contexts:
                prompt_with_memories = self._inject_kb_contexts(prompt_with_memories, kb_contexts)

        return ContextPayload(
            system_prompt=prompt_with_memories,
            recent_conversation=recent_conversation or [],
            retrieved_memories=retrieved_memories,
            current_user_message=user_message,
        )

    def _inject_kb_contexts(self, system_prompt: str, kb_contexts: List[str]) -> str:
        lines = [
            system_prompt.rstrip(),
            "",
            "Relevant Document Context:",
            "Use the following information from uploaded documents if it helps answer the user's request. Keep answers natural and friendly. If the document content is not relevant, continue conversation normally.",
        ]
        lines.extend(kb_contexts)
        self._logger.info("KB: Injected document context count=%d into system prompt", len(kb_contexts))
        return "\n".join(lines)

    def _inject_memories(self, system_prompt: str, memories: List[Any]) -> str:
        if not memories:
            self._logger.info("Memory injected into prompt count=0")
            return system_prompt

        lines = [
            system_prompt.rstrip(),
            "",
            "Known User Information:",
        ]
        for memory in memories[:10]:
            category_value = getattr(memory, "category", "memory")
            category = category_value.value if hasattr(category_value, "value") else str(category_value)
            key = getattr(memory, "key", "note")
            value = getattr(memory, "value", None)
            if value is None:
                value = getattr(memory, "content", "")
            lines.append(f"- [{category}] {key}: {value}")

        self._logger.info("Memory injected into prompt count=%d", min(len(memories), 10))
        return "\n".join(lines)
