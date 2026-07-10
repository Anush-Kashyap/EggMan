from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# Import modules package to trigger self-registration of modules
import backend.prompt.modules
from backend.prompt.prompt_cache import PromptCache
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry

logger = logging.getLogger("eggman")


@dataclass
class PromptStats:
    """Contains diagnostic details for prompt compilation."""
    total_tokens: int = 0
    total_chars: int = 0
    modules_used: List[str] = field(default_factory=list)
    module_tokens: Dict[str, int] = field(default_factory=dict)
    module_chars: Dict[str, int] = field(default_factory=dict)
    module_generation_times: Dict[str, float] = field(default_factory=dict)
    cache_hits: int = 0
    cache_misses: int = 0
    build_duration_ms: float = 0.0
    reduction_percentage: float = 0.0


class PromptBuilder:
    """Orchestrates system prompt construction using registered modules and caching."""

    _last_stats: Optional[PromptStats] = None

    @classmethod
    def get_last_stats(cls) -> Optional[PromptStats]:
        """Access stats of the most recently built prompt."""
        return cls._last_stats

    def __init__(
        self,
        retrieval_service: Any = None,
        knowledge_manager: Any = None,
    ) -> None:
        self._retrieval_service = retrieval_service
        self._knowledge_manager = knowledge_manager
        self._cache = PromptCache()
        self._logger = logger

    def build_system_prompt(
        self,
        mode: str,
        is_voice: bool,
        user_message: str,
        persona_prompt: Optional[str] = None,
    ) -> str:
        """Assembles prompt sections dynamically based on current context."""
        t_start = time.perf_counter()
        self._logger.info("PromptBuilder v2: Assembling prompt mode=%s, voice=%s", mode, is_voice)

        # 1. Build the prompt context
        context = self._create_context(mode, is_voice, user_message, persona_prompt)

        # 2. Collect applicable modules and compile them
        sections = []
        modules = PromptRegistry.get_modules()

        used_module_names = []
        module_tokens = {}
        module_chars = {}
        module_times = {}

        total_possible_chars = 0

        for module in modules:
            # Generate potential possible content size for reduction calculation
            if module.name() in ("identity", "communication", "persona", "tools", "scheduler", "vision", "developer"):
                total_possible_chars += len(module.generate(context))

            if not module.is_applicable(context):
                continue

            used_module_names.append(module.name())
            t_mod_start = time.perf_counter()

            # Cache handling
            content = None
            cache_key = f"{module.name()}:{context.is_voice}:{context.mode}"
            if module.is_static():
                content = self._cache.get(cache_key)

            if content is None:
                content = module.generate(context)
                if module.is_static():
                    self._cache.set(cache_key, content)

            mod_duration = (time.perf_counter() - t_mod_start) * 1000
            module_times[module.name()] = mod_duration

            # Stats per module
            char_count = len(content)
            token_count = char_count // 4  # Heuristic token count
            module_chars[module.name()] = char_count
            module_tokens[module.name()] = token_count

            sections.append(content)

        # 3. Dynamic mode details (appended cleanly if present)
        mode_section = f"CONVERSATION MODE: {mode.upper()}\n"
        if mode == "casual":
            mode_section += "- Keep your responses relaxed, short, and natural."
        elif mode == "teaching":
            mode_section += "- Keep your responses structured, clear, educational, and detailed when required."
        elif mode == "programming":
            mode_section += "- Keep your responses direct, technical, and highly efficient. Focus on code correctness without fluff."
        sections.append(mode_section)

        # 4. Response length constraints based on small talk/greetings
        length_constraint = self._get_length_constraint(user_message)
        if length_constraint:
            sections.append(length_constraint)

        final_prompt = "\n\n".join(sections)

        # Compile final stats
        build_duration = (time.perf_counter() - t_start) * 1000
        total_chars = len(final_prompt)
        total_tokens = total_chars // 4

        reduction_percentage = 0.0
        if total_possible_chars > 0:
            reduction_percentage = max(0.0, (1.0 - (total_chars / total_possible_chars)) * 100)

        stats = PromptStats(
            total_tokens=total_tokens,
            total_chars=total_chars,
            modules_used=used_module_names,
            module_tokens=module_tokens,
            module_chars=module_chars,
            module_generation_times=module_times,
            cache_hits=self._cache.hits,
            cache_misses=self._cache.misses,
            build_duration_ms=build_duration,
            reduction_percentage=reduction_percentage,
        )
        PromptBuilder._last_stats = stats

        # Developer Mode Logging
        from backend.session.session_manager import SessionManager
        session_ctx = SessionManager.get_instance().context
        if session_ctx.developer_mode:
            self._logger.info(
                "[DEV MODE] Prompt Built | Modules: %s | Tokens: %d | Chars: %d | Hits: %d | Misses: %d | Time: %.2fms",
                ", ".join(used_module_names),
                total_tokens,
                total_chars,
                stats.cache_hits,
                stats.cache_misses,
                build_duration,
            )

        return final_prompt

    def _create_context(
        self,
        mode: str,
        is_voice: bool,
        user_message: str,
        persona_prompt: Optional[str] = None,
    ) -> PromptContext:
        """Helper to build PromptContext using session settings and active retrievers."""
        from backend.session.session_manager import SessionManager
        session = SessionManager.get_instance().context

        # Check image presence
        has_image = bool(session.pending_attachment)

        # Check tool availability (route tool requests)
        has_tools = False
        from app.container import AppContainer
        # We can dynamically check if AppContainer has tools registered
        # Or look for indicators in current prompt/message context
        msg_lower = user_message.lower()
        if any(w in msg_lower for w in ["open", "calc", "calculate", "math", "launch"]):
            has_tools = True

        # Check scheduler involvement
        has_scheduler = False
        if any(w in msg_lower for w in ["schedule", "remind", "alarm", "task", "todo", "calendar"]):
            has_scheduler = True

        # Lazily fetch memories & knowledge if appropriate for the query
        memories = []
        knowledge = []
        is_trivial = len(user_message.split()) < 3 or any(w in msg_lower for w in ["hello", "hi", "thanks", "ok"])

        if self._retrieval_service and not is_trivial:
            memories = self._retrieval_service.retrieve(user_message, limit=3)

        if self._knowledge_manager and not is_trivial:
            knowledge = self._knowledge_manager.search(user_message)

        return PromptContext(
            user_message=user_message,
            mode=mode,
            is_voice=is_voice,
            persona_prompt=persona_prompt,
            has_image=has_image,
            has_tools=has_tools,
            has_scheduler=has_scheduler,
            developer_mode=session.developer_mode,
            retrieved_memories=memories,
            retrieved_knowledge=knowledge,
        )

    def _get_length_constraint(self, user_message: str) -> str:
        msg_lower = user_message.strip().lower().rstrip("?.!")
        greetings = ["hello", "hi", "hey", "morning", "evening", "greetings", "yo"]
        small_talk = ["how are you", "what's up", "how's it going", "how are you doing", "what are you up to"]

        if msg_lower in greetings:
            return "RESPONSE LENGTH CONSTRAINT:\n- Limit your response to exactly 1 sentence (e.g., a simple warm greeting)."
        elif any(st in msg_lower for st in small_talk):
            return "RESPONSE LENGTH CONSTRAINT:\n- Limit your response to 1-2 sentences maximum."

        return ""
