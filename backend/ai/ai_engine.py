from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from backend.ai.models import AIRequest, AIResponse
from backend.ai.provider_registry import ProviderRegistry
from backend.ai.streaming import StreamingResponse
from backend.context.context_builder import ContextBuilder
from backend.memory.memory_manager import MemoryManager
from backend.tools.router import ToolRouter
from core.providers import BaseProvider


@dataclass(slots=True)
class AIRequestConversationEntry:
    sender: str
    text: str


class AIEngine:
    """Orchestrates request handling, provider execution, and memory updates."""

    def __init__(
        self,
        context_builder: ContextBuilder,
        memory_manager: MemoryManager,
        provider_registry: ProviderRegistry,
        tool_router: ToolRouter | None = None,
        logger: Optional[logging.Logger] = None,
    ) -> None:
        self._context_builder = context_builder
        self._memory_manager = memory_manager
        self._provider_registry = provider_registry
        self._tool_router = tool_router
        self._logger = logger or logging.getLogger(__name__)

    def _resolve_provider(self) -> Optional[BaseProvider]:
        self._logger.debug(
            "AIEngine._resolve_provider entering active=%s available=%s",
            self._provider_registry.active_provider_name(),
            self._provider_registry.available_providers(),
        )
        provider_cls = self._provider_registry.get()
        if provider_cls is None:
            self._logger.error("No active AI provider is registered.")
            return None
        try:
            provider = provider_cls()
        except Exception as exc:
            self._logger.exception("Provider initialization failed active=%s error=%s", self._provider_registry.active_provider_name(), exc)
            return None
        self._logger.info("Resolved provider: %s", provider.provider_name)

        # Register resolved provider to SessionContext
        provider_name = self._provider_registry.active_provider_name()
        from backend.session.session_manager import SessionManager
        SessionManager.get_instance().context.active_provider = provider_name

        return provider

    def generate(self, request: AIRequest) -> AIResponse:
        """Generate a full-text response from the active provider."""
        start = time.perf_counter()
        
        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        profile = profiler.start_request(request.user_message)
        
        self._logger.info(
            "AI request received provider=%s message_len=%d",
            self._provider_registry.active_provider_name(),
            len(request.user_message or ""),
        )
        self._logger.debug("AIEngine.generate entering")

        # Save user message to SessionContext
        from backend.session.session_manager import SessionManager
        session = SessionManager.get_instance().context
        session.last_user_message = request.user_message

        routed_response = self._route_tool_request(request)
        if routed_response is not None:
            session.last_ai_message = routed_response.response_text
            profiler.finalize_request(
                model_name="ToolRouter",
                memory_used=profile.memory_used if profile else False,
                knowledge_used=profile.knowledge_used if profile else False,
                vision_used=profile.vision_used if profile else False,
                tools_executed=profile.tools_executed if profile else False
            )
            return routed_response

        provider = self._resolve_provider()
        if provider is None:
            profiler.finalize_request(model_name="Error")
            return AIResponse(error="No active provider available")

        prompt_payload = self._build_request_with_context(request)
        try:
            self._logger.info("AIEngine generating response")
            response = provider.generate(prompt_payload)
            self._logger.debug(
                "AIEngine.generate provider returned in %.1fms successful=%s error=%s text_len=%d",
                (time.perf_counter() - start) * 1000,
                response.successful,
                response.error,
                len(str(response.response_text or "")),
            )
            if response.successful:
                self._trigger_memory(prompt_payload)
                session.active_chat_model = response.model_name
                session.last_ai_message = response.response_text
            
            # Finalize profiling
            profiler.finalize_request(
                model_name=response.model_name or provider.model_name or "Unknown",
                memory_used=profile.memory_used if profile else False,
                knowledge_used=profile.knowledge_used if profile else False,
                vision_used=profile.vision_used if profile else False,
                tools_executed=profile.tools_executed if profile else False
            )
            return response
        except Exception as exc:
            self._logger.exception("AI generation failed: %s", exc)
            profiler.finalize_request(model_name="Error")
            return AIResponse(error=str(exc), provider_name=provider.provider_name)

    def stream(self, request: AIRequest) -> StreamingResponse:
        """Return a streaming response from the active provider."""
        provider = self._resolve_provider()
        if provider is None:
            return StreamingResponse(chunks=["Error: no provider available"])

        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        profile = profiler.start_request(request.user_message)

        prompt_payload = self._build_request_with_context(request)
        self._logger.info("AIEngine initiating stream")
        try:
            original_stream = provider.stream(prompt_payload)
            return StreamingResponse(chunks=self._wrap_stream(original_stream, profiler))
        except Exception as exc:
            self._logger.error(f"AI stream failed: {exc}")
            profiler.finalize_request(model_name="Error")
            return StreamingResponse(chunks=[f"Error: {exc}"])

    def _wrap_stream(self, original_stream: Any, profiler: PerformanceProfiler) -> Iterable[str]:
        profile = profiler.get_current_profile()
        try:
            for chunk in original_stream.chunks:
                yield chunk
        finally:
            profiler.finalize_request(
                model_name=getattr(original_stream, "model_name", None) or "Unknown",
                memory_used=profile.memory_used if profile else False,
                knowledge_used=profile.knowledge_used if profile else False,
                vision_used=profile.vision_used if profile else False,
                tools_executed=profile.tools_executed if profile else False
            )

    def _build_request_with_context(self, request: AIRequest) -> AIRequest:
        start = time.perf_counter()
        self._logger.debug("AIEngine._build_request_with_context entering")
        context = self._context_builder.build_context(
            user_message=request.user_message,
            recent_conversation=[(entry.sender, entry.text) for entry in request.conversation_history],
            memories=request.memories,
            system_prompt=request.system_prompt,
        )
        request.system_prompt = context.system_prompt
        request.conversation_history = [
            AIRequestConversationEntry(sender=sender, text=text)
            for sender, text in context.recent_conversation
        ]
        request.memories = context.retrieved_memories
        self._logger.debug(
            "AIEngine._build_request_with_context leaving in %.1fms history=%d memories=%d",
            (time.perf_counter() - start) * 1000,
            len(request.conversation_history),
            len(request.memories),
        )
        return request

    def _trigger_memory(self, request: AIRequest) -> None:
        try:
            if request.user_message:
                memory = self._memory_manager.extract_and_store(request.user_message)
                if memory is not None:
                    self._logger.info("Memory extracted after AI response id=%s key=%s", memory.id, memory.key)
        except Exception as exc:
            self._logger.exception("Memory trigger failed: %s", exc)

    def _route_tool_request(self, request: AIRequest) -> AIResponse | None:
        if self._tool_router is None or not request.user_message:
            return None

        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        profiler.start_stage("Tool Execution")
        route_result = self._tool_router.route(request.user_message)
        profiler.stop_stage("Tool Execution")

        if not route_result.handled:
            return None

        profile = profiler.get_current_profile()
        if profile:
            profile.tools_executed = True

        self._logger.info("AIEngine short-circuited request with tool=%s", route_result.tool_name)
        return AIResponse(
            response_text=route_result.response_text,
            finish_reason="tool",
            provider_name=f"tool:{route_result.tool_name}",
            metadata={"tool_result": route_result.result},
        )
