from __future__ import annotations

import logging
from time import perf_counter
from backend.ai.ai_engine import AIEngine
from backend.ai.models import AIRequest, MessageEntry
from backend.ai.prompt_builder import PromptBuilder
from backend.ai.streaming import StreamingResponse
from core.providers import LocalProvider

logger = logging.getLogger("eggman")


class ConversationEngine:
    def __init__(self, ai_engine: AIEngine | None = None):
        self._ai_engine = ai_engine
        self._fallback_provider = LocalProvider()
        self._prompt_builder = PromptBuilder()

    def get_reply(
        self,
        user_message: str,
        images: list[str] | None = None,
        history: list[tuple[str, str]] | None = None
    ) -> str:
        start = perf_counter()

        # Update SessionContext values
        from backend.session.session_manager import SessionManager
        session = SessionManager.get_instance().context
        if not session.conversation_id:
            session.conversation_id = "default_session_conv"

        # Simple emotion detection based on message text
        msg_lower = user_message.lower()
        if any(w in msg_lower for w in ["happy", "great", "awesome", "good", "nice"]):
            session.current_emotion = "happy"
        elif any(w in msg_lower for w in ["sad", "bad", "sorry", "unhappy"]):
            session.current_emotion = "sad"
        elif any(w in msg_lower for w in ["angry", "mad", "hate", "annoyed"]):
            session.current_emotion = "angry"
        else:
            session.current_emotion = "neutral"

        # Detect dynamic intent mode (casual, teaching, programming)
        mode = self._detect_mode(user_message)
        
        # Check if voice mode is active
        is_voice = bool(session.get_temporary_value("voice_mode", False))

        # Dynamically build system prompt from modules
        from backend.profiler.performance_profiler import PerformanceProfiler
        from backend.personas.persona_manager import PersonaManager
        PerformanceProfiler.get_instance().start_stage("Prompt Builder")
        persona_manager = PersonaManager.get_instance()
        persona_prompt = persona_manager.get_active_persona_prompt()
        system_prompt = self._prompt_builder.build_system_prompt(mode, is_voice, user_message, persona_prompt)
        PerformanceProfiler.get_instance().stop_stage("Prompt Builder")

        # Convert history tuples to MessageEntry list
        history_entries = []
        if history:
            for sender, text in history:
                history_entries.append(MessageEntry(sender=sender, text=text))

        if self._ai_engine is None:
            response = self._fallback_provider.generate(
                AIRequest(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    conversation_history=history_entries,
                    images=images or []
                )
            )
            reply = response.response_text if hasattr(response, 'response_text') else str(response)
            return str(reply).strip() if reply else "I'm thinking..."

        request = AIRequest(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=history_entries,
            images=images or [],
            metadata={"classification": mode}
        )
        
        response = self._ai_engine.generate(request)
        elapsed_ms = (perf_counter() - start) * 1000
        
        self._ai_engine._logger.debug(
            "ConversationEngine.get_reply completed in %.1fms successful=%s error=%s",
            elapsed_ms,
            response.successful,
            response.error,
        )

        # Developer Mode Logging
        if session.developer_mode:
            tokens_sent = response.token_usage.prompt_tokens if (response.token_usage and hasattr(response.token_usage, 'prompt_tokens')) else 0
            tokens_received = response.token_usage.completion_tokens if (response.token_usage and hasattr(response.token_usage, 'completion_tokens')) else 0
            
            logger.info("[DEV MODE] Tokens sent: %d", tokens_sent)
            logger.info("[DEV MODE] Tokens received: %d", tokens_received)
            logger.info("[DEV MODE] Response latency: %.1f ms", elapsed_ms)
            from backend.personas.persona_manager import PersonaManager
            PersonaManager.get_instance().log_developer_info()

        if response.successful:
            reply = response.response_text if hasattr(response, 'response_text') else str(response)
            return str(reply).strip() if reply else "I'm thinking..."
            
        return f"Sorry, something went wrong: {response.error or 'unknown error'}"

    def stream_reply(
        self,
        user_message: str,
        images: list[str] | None = None,
        history: list[tuple[str, str]] | None = None
    ) -> StreamingResponse:
        from backend.session.session_manager import SessionManager
        session = SessionManager.get_instance().context
        if not session.conversation_id:
            session.conversation_id = "default_session_conv"

        msg_lower = user_message.lower()
        if any(w in msg_lower for w in ["happy", "great", "awesome", "good", "nice"]):
            session.current_emotion = "happy"
        elif any(w in msg_lower for w in ["sad", "bad", "sorry", "unhappy"]):
            session.current_emotion = "sad"
        elif any(w in msg_lower for w in ["angry", "mad", "hate", "annoyed"]):
            session.current_emotion = "angry"
        else:
            session.current_emotion = "neutral"

        mode = self._detect_mode(user_message)
        is_voice = bool(session.get_temporary_value("voice_mode", False))

        from backend.profiler.performance_profiler import PerformanceProfiler
        from backend.personas.persona_manager import PersonaManager
        PerformanceProfiler.get_instance().start_stage("Prompt Builder")
        persona_prompt = PersonaManager.get_instance().get_active_persona_prompt()
        system_prompt = self._prompt_builder.build_system_prompt(mode, is_voice, user_message, persona_prompt)
        PerformanceProfiler.get_instance().stop_stage("Prompt Builder")

        history_entries = []
        if history:
            for sender, text in history:
                history_entries.append(MessageEntry(sender=sender, text=text))

        request = AIRequest(
            system_prompt=system_prompt,
            user_message=user_message,
            conversation_history=history_entries,
            images=images or [],
            metadata={"classification": mode}
        )

        if self._ai_engine is None:
            # Fallback provider (LocalProvider) doesn't natively stream, yield single response
            response = self._fallback_provider.generate(request)
            reply = response.response_text if hasattr(response, 'response_text') else str(response)
            return StreamingResponse(chunks=[reply])

        # Tool Routing Check
        tool_res = self._ai_engine._route_tool_request(request)
        if tool_res is not None:
            session.last_ai_message = tool_res.response_text
            PerformanceProfiler.get_instance().finalize_request(
                model_name="ToolRouter",
                tools_executed=True
            )
            return StreamingResponse(chunks=[tool_res.response_text])

        return self._ai_engine.stream(request)

    def _detect_mode(self, user_message: str) -> str:
        msg_lower = user_message.lower()
        
        # Programming cues
        programming_keywords = [
            "code", "bug", "error", "exception", "function", "class", "compile", 
            "python", "javascript", "c++", "rust", "html", "css", "git", "database", 
            "sql", "api", "json", "array", "list", "loop", "variable", "import", "def "
        ]
        if any(kw in msg_lower for kw in programming_keywords):
            return "programming"
            
        # Teaching cues
        teaching_keywords = [
            "explain", "teach", "how does", "why does", "what is", "tutorial", 
            "understand", "concept", "difference between"
        ]
        if any(kw in msg_lower for kw in teaching_keywords):
            return "teaching"
            
        return "casual"
