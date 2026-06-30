from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger("eggman")


class SessionContext:
    """Manages the temporary runtime state of the application in a thread-safe manner."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._conversation_id: Optional[str] = None
        self._pending_attachment: Optional[Any] = None
        self._active_provider: Optional[str] = None
        self._active_chat_model: Optional[str] = None
        self._active_vision_model: Optional[str] = None
        self._voice_state: Optional[str] = "idle"
        self._wake_word_enabled: bool = False
        self._is_listening: bool = False
        self._developer_mode: bool = False
        self._current_emotion: str = "neutral"
        self._last_user_message: Optional[str] = None
        self._last_ai_message: Optional[str] = None

        # Generic dicts for future compatibility (scheduler, plugins, downloads, etc.)
        self.temporary_context: Dict[str, Any] = {}
        self.runtime_flags: Dict[str, Any] = {}

        logger.info("SessionContext: session created")

    @property
    def conversation_id(self) -> Optional[str]:
        with self._lock:
            return self._conversation_id

    @conversation_id.setter
    def conversation_id(self, val: Optional[str]) -> None:
        with self._lock:
            if self._conversation_id != val:
                logger.info("SessionContext: State updated - conversation_id from %s to %s", self._conversation_id, val)
                self._conversation_id = val

    @property
    def pending_attachment(self) -> Optional[Any]:
        with self._lock:
            return self._pending_attachment

    @pending_attachment.setter
    def pending_attachment(self, val: Optional[Any]) -> None:
        with self._lock:
            if self._pending_attachment is None and val is not None:
                logger.info("SessionContext: Attachment added")
            elif self._pending_attachment is not None and val is None:
                logger.info("SessionContext: Attachment removed")
            elif self._pending_attachment != val:
                logger.info("SessionContext: Attachment updated")
            self._pending_attachment = val

    @property
    def active_provider(self) -> Optional[str]:
        with self._lock:
            return self._active_provider

    @active_provider.setter
    def active_provider(self, val: Optional[str]) -> None:
        with self._lock:
            if self._active_provider != val:
                logger.info("SessionContext: Provider/model changes - active_provider updated from %s to %s", self._active_provider, val)
                self._active_provider = val

    @property
    def active_chat_model(self) -> Optional[str]:
        with self._lock:
            return self._active_chat_model

    @active_chat_model.setter
    def active_chat_model(self, val: Optional[str]) -> None:
        with self._lock:
            if self._active_chat_model != val:
                logger.info("SessionContext: Provider/model changes - active_chat_model updated from %s to %s", self._active_chat_model, val)
                self._active_chat_model = val

    @property
    def active_vision_model(self) -> Optional[str]:
        with self._lock:
            return self._active_vision_model

    @active_vision_model.setter
    def active_vision_model(self, val: Optional[str]) -> None:
        with self._lock:
            if self._active_vision_model != val:
                logger.info("SessionContext: Provider/model changes - active_vision_model updated from %s to %s", self._active_vision_model, val)
                self._active_vision_model = val

    @property
    def voice_state(self) -> Optional[str]:
        with self._lock:
            return self._voice_state

    @voice_state.setter
    def voice_state(self, val: Optional[str]) -> None:
        with self._lock:
            if self._voice_state != val:
                logger.info("SessionContext: Voice state changes - voice_state updated from %s to %s", self._voice_state, val)
                self._voice_state = val

    @property
    def wake_word_enabled(self) -> bool:
        with self._lock:
            return self._wake_word_enabled

    @wake_word_enabled.setter
    def wake_word_enabled(self, val: bool) -> None:
        with self._lock:
            if self._wake_word_enabled != val:
                logger.info("SessionContext: State updated - wake_word_enabled updated from %s to %s", self._wake_word_enabled, val)
                self._wake_word_enabled = val

    @property
    def is_listening(self) -> bool:
        with self._lock:
            return self._is_listening

    @is_listening.setter
    def is_listening(self, val: bool) -> None:
        with self._lock:
            if self._is_listening != val:
                logger.info("SessionContext: State updated - is_listening updated from %s to %s", self._is_listening, val)
                self._is_listening = val

    @property
    def developer_mode(self) -> bool:
        with self._lock:
            return self._developer_mode

    @developer_mode.setter
    def developer_mode(self, val: bool) -> None:
        with self._lock:
            if self._developer_mode != val:
                logger.info("SessionContext: State updated - developer_mode updated from %s to %s", self._developer_mode, val)
                self._developer_mode = val

    @property
    def current_emotion(self) -> str:
        with self._lock:
            return self._current_emotion

    @current_emotion.setter
    def current_emotion(self, val: str) -> None:
        with self._lock:
            if self._current_emotion != val:
                logger.info("SessionContext: State updated - current_emotion updated from %s to %s", self._current_emotion, val)
                self._current_emotion = val

    @property
    def last_user_message(self) -> Optional[str]:
        with self._lock:
            return self._last_user_message

    @last_user_message.setter
    def last_user_message(self, val: Optional[str]) -> None:
        with self._lock:
            if self._last_user_message != val:
                logger.info("SessionContext: State updated - last_user_message updated")
                self._last_user_message = val

    @property
    def last_ai_message(self) -> Optional[str]:
        with self._lock:
            return self._last_ai_message

    @last_ai_message.setter
    def last_ai_message(self, val: Optional[str]) -> None:
        with self._lock:
            if self._last_ai_message != val:
                logger.info("SessionContext: State updated - last_ai_message updated")
                self._last_ai_message = val
