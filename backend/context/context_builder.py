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
        recent_conv = recent_conversation or []
        older_conv = []
        
        # Split history: keep only last 6 turns (3 roundtrips) to prevent prompt bloat
        if len(recent_conv) > 6:
            older_conv = recent_conv[:-6]
            recent_conv = recent_conv[-6:]

        retrieved_memories = memories or []
        if self._retrieval_service is not None:
            from backend.profiler.performance_profiler import PerformanceProfiler
            PerformanceProfiler.get_instance().start_stage("Memory Retrieval")
            retrieved_memories = self._retrieval_service.retrieve(user_message)
            PerformanceProfiler.get_instance().stop_stage("Memory Retrieval")
        
        base_prompt = system_prompt or "You are EggMan, a friendly desktop companion."
        
        # Add conversation summary if we have older history
        summary_str = self._generate_lightweight_summary(older_conv)
        if summary_str:
            base_prompt = base_prompt.rstrip() + f"\n\nCONVERSATION SUMMARY (Earlier Turns):\n{summary_str}"

        prompt_with_memories = self._inject_memories(base_prompt, retrieved_memories)

        # Inject KB document context if available (semantic or keyword fallback)
        kb_injected = False
        if self._knowledge_manager is not None:
            from backend.profiler.performance_profiler import PerformanceProfiler
            perf = PerformanceProfiler.get_instance()
            perf.start_stage("Knowledge Retrieval")
            kb_contexts = self._knowledge_manager.search(user_message)
            perf.stop_stage("Knowledge Retrieval")
            if kb_contexts:
                prompt_with_memories = self._inject_kb_contexts(prompt_with_memories, kb_contexts)
                kb_injected = True

        from backend.profiler.performance_profiler import PerformanceProfiler
        profile = PerformanceProfiler.get_instance().get_current_profile()
        if profile:
            if retrieved_memories:
                profile.memory_used = True
            if kb_injected:
                profile.knowledge_used = True

        # Developer Mode Logging
        from backend.session.session_manager import SessionManager
        session_ctx = SessionManager.get_instance().context
        if session_ctx.developer_mode:
            self._logger.info("[DEV MODE] Prompt sections assembled")
            self._logger.info("[DEV MODE] Context size: %d chars", len(user_message) + len(prompt_with_memories))
            self._logger.info("[DEV MODE] Memory retrieval: query='%s'", user_message)
            self._logger.info("[DEV MODE] Memories injected: %d", len(retrieved_memories))
            self._logger.info("[DEV MODE] Knowledge injected: %s", "Yes" if kb_injected else "No")
            self._logger.info("[DEV MODE] Conversation summary size: %d chars", len(summary_str))

        return ContextPayload(
            system_prompt=prompt_with_memories,
            recent_conversation=recent_conv,
            retrieved_memories=retrieved_memories,
            current_user_message=user_message,
        )

    def _generate_lightweight_summary(self, older_conversation: List[tuple[str, str]]) -> str:
        if not older_conversation:
            return ""
        
        summaries = []
        for sender, text in older_conversation:
            text_preview = text.strip()
            first_line = text_preview.split("\n")[0]
            if len(first_line) > 60:
                first_line = first_line[:60] + "..."
            summaries.append(f"{sender}: {first_line}")
            
        return "\n".join(summaries[-8:])

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
        
        # Group memories by category
        grouped: dict[str, list[Any]] = {}
        for memory in memories[:10]:
            category_value = getattr(memory, "category", "memory")
            category = category_value.value if hasattr(category_value, "value") else str(category_value)
            grouped.setdefault(category, []).append(memory)

        for category, mem_list in grouped.items():
            lines.append(f"  {category.replace('_', ' ').title()}:")
            for memory in mem_list:
                value = getattr(memory, "value", None)
                if value is None:
                    value = getattr(memory, "content", "")
                
                confidence = getattr(memory, "confidence", 1.0)
                if confidence < 0.7:
                    lines.append(f"    - (Possible) {value}")
                else:
                    lines.append(f"    - {value}")

        self._logger.info("Memory injected into prompt count=%d", min(len(memories), 10))
        return "\n".join(lines)
