from __future__ import annotations

import threading
from typing import Any, Optional
from backend.session.session_context import SessionContext


class SessionManager:
    """Singleton manager for the SessionContext, providing thread-safe operations."""

    _instance: Optional[SessionManager] = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs) -> SessionManager:
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._context = SessionContext()
        return cls._instance

    @classmethod
    def get_instance(cls) -> SessionManager:
        """Access the global SessionManager singleton."""
        return cls()

    @property
    def context(self) -> SessionContext:
        """Retrieve the managed SessionContext."""
        return self._context

    def update_value(self, name: str, val: Any) -> None:
        """Safely set a attribute on the context."""
        with self._lock:
            setattr(self._context, name, val)

    def reset_temp_state(self) -> None:
        """Reset temporary session states safely."""
        with self._lock:
            self._context.pending_attachment = None
            self._context.last_user_message = None
            self._context.last_ai_message = None
            self._context.temporary_context.clear()
            self._context.runtime_flags.clear()

    def set_temporary_value(self, key: str, val: Any) -> None:
        """Safely set a key-value pair in context temporary_context dictionary."""
        with self._lock:
            self._context.set_temporary_value(key, val)

    def get_temporary_value(self, key: str, default: Any = None) -> Any:
        """Safely get a value from context temporary_context dictionary."""
        with self._lock:
            return self._context.get_temporary_value(key, default)

    def set_runtime_flag(self, key: str, val: Any) -> None:
        """Safely set a key-value pair in context runtime_flags dictionary."""
        with self._lock:
            self._context.set_runtime_flag(key, val)

    def get_runtime_flag(self, key: str, default: Any = None) -> Any:
        """Safely get a value from context runtime_flags dictionary."""
        with self._lock:
            return self._context.get_runtime_flag(key, default)
