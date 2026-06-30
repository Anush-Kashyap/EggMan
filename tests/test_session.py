from __future__ import annotations

import threading
import pytest
from backend.session.session_manager import SessionManager
from backend.session.session_context import SessionContext


def test_session_manager_singleton():
    """Verify that SessionManager is a strict singleton."""
    mgr1 = SessionManager.get_instance()
    mgr2 = SessionManager()
    assert mgr1 is mgr2
    assert mgr1.context is mgr2.context


def test_session_context_property_updates():
    """Verify that SessionContext values update and read correctly."""
    mgr = SessionManager.get_instance()
    ctx = mgr.context

    # Update state variables
    ctx.conversation_id = "test_conv"
    assert ctx.conversation_id == "test_conv"

    ctx.active_provider = "gemini"
    assert ctx.active_provider == "gemini"

    ctx.active_chat_model = "gemini-2.5-flash"
    assert ctx.active_chat_model == "gemini-2.5-flash"

    ctx.active_vision_model = "gemini-2.5-vision"
    assert ctx.active_vision_model == "gemini-2.5-vision"

    ctx.voice_state = "listening"
    assert ctx.voice_state == "listening"

    ctx.wake_word_enabled = True
    assert ctx.wake_word_enabled is True

    ctx.is_listening = True
    assert ctx.is_listening is True

    ctx.developer_mode = True
    assert ctx.developer_mode is True

    ctx.current_emotion = "happy"
    assert ctx.current_emotion == "happy"

    ctx.last_user_message = "Hello EggMan"
    assert ctx.last_user_message == "Hello EggMan"

    ctx.last_ai_message = "Hello user!"
    assert ctx.last_ai_message == "Hello user!"

    ctx.pending_attachment = "image_base64_data"
    assert ctx.pending_attachment == "image_base64_data"


def test_session_manager_reset():
    """Verify that resetting temporary state clears fields correctly."""
    mgr = SessionManager.get_instance()
    ctx = mgr.context

    ctx.pending_attachment = "base64"
    ctx.last_user_message = "hello"
    ctx.last_ai_message = "hi"
    ctx.temporary_context["test_key"] = "test_val"
    ctx.runtime_flags["flag_key"] = True

    mgr.reset_temp_state()

    assert ctx.pending_attachment is None
    assert ctx.last_user_message is None
    assert ctx.last_ai_message is None
    assert len(ctx.temporary_context) == 0
    assert len(ctx.runtime_flags) == 0


def test_session_context_thread_safety():
    """Verify that concurrent thread updates do not crash or cause race conditions."""
    mgr = SessionManager.get_instance()
    ctx = mgr.context

    def update_worker(val_str: str):
        for _ in range(100):
            ctx.conversation_id = val_str
            ctx.temporary_context[val_str] = val_str
            ctx.runtime_flags[val_str] = True

    threads = []
    for i in range(10):
        t = threading.Thread(target=update_worker, args=(f"thread_{i}",))
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    # Just verify that dictionary lengths are correct and no deadlock occurred
    assert len(ctx.temporary_context) >= 10
    assert len(ctx.runtime_flags) >= 10
