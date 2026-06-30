from backend.ai.ai_engine import AIEngine
from backend.ai.models import AIRequest
from core.providers import LocalProvider
from time import perf_counter


class ConversationEngine:
    def __init__(self, ai_engine: AIEngine | None = None):
        self._ai_engine = ai_engine
        self._fallback_provider = LocalProvider()

    def get_reply(self, user_message: str, images: list[str] | None = None) -> str:
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

        if self._ai_engine is None:
            response = self._fallback_provider.generate(AIRequest(user_message=user_message, images=images or []))
            reply = response.response_text if hasattr(response, 'response_text') else str(response)
            return str(reply).strip() if reply else "I'm thinking..."

        request = AIRequest(user_message=user_message, images=images or [])
        response = self._ai_engine.generate(request)
        elapsed_ms = (perf_counter() - start) * 1000
        self._ai_engine._logger.debug(
            "ConversationEngine.get_reply completed in %.1fms successful=%s error=%s",
            elapsed_ms,
            response.successful,
            response.error,
        )
        if response.successful:
            reply = response.response_text if hasattr(response, 'response_text') else str(response)
            return str(reply).strip() if reply else "I'm thinking..."
        return f"Sorry, something went wrong: {response.error or 'unknown error'}"
