"""Tests for StartupService (Startup System v2)."""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch
import pytest

from backend.startup.startup_service import StartupService, StartupState, StartupProfile


# ---------------------------------------------------------------------------
# StartupProfile tests
# ---------------------------------------------------------------------------

class TestStartupProfile:
    def test_start_and_stop_stage(self):
        profile = StartupProfile()
        profile.start_stage("A")
        time.sleep(0.01)
        profile.stop_stage("A")
        assert "A" in profile.stages
        assert profile.stages["A"] >= 0.01

    def test_stop_stage_without_start_is_noop(self):
        profile = StartupProfile()
        profile.stop_stage("NonExistent")  # should not raise
        assert "NonExistent" not in profile.stages

    def test_finalize_sets_status(self):
        profile = StartupProfile()
        profile.finalize(StartupState.READY)
        assert profile.status == "READY"
        assert profile.total_time >= 0.0

    def test_finalize_closes_open_stages(self):
        profile = StartupProfile()
        profile.start_stage("Orphan")
        profile.finalize(StartupState.ERROR)
        # Orphan stage should have been closed by finalize
        assert "Orphan" in profile.stages


# ---------------------------------------------------------------------------
# StartupService tests
# ---------------------------------------------------------------------------

def _make_container():
    """Build a minimal mock AppContainer."""
    container = MagicMock()
    container.ollama_startup_error = None
    container.settings_manager.get.return_value = False
    container.config_manager.get.return_value = "test-value"
    container.task_repository.get_all_tasks.return_value = []
    return container


class TestStartupService:
    def test_initial_state_is_initializing(self):
        svc = StartupService(_make_container())
        assert svc.state == StartupState.INITIALIZING
        assert not svc.is_ready

    def test_should_block_ai_message_during_init(self):
        svc = StartupService(_make_container())
        assert svc.should_block_message("hello world")

    def test_should_not_block_slash_commands_during_init(self):
        svc = StartupService(_make_container())
        for cmd in ["/help", "/dev", "/schedule", "/file"]:
            assert not svc.should_block_message(cmd), f"Expected {cmd} to pass through"

    def test_should_not_block_anything_when_ready(self):
        svc = StartupService(_make_container())
        # Manually force READY
        with svc._lock:
            svc._state = StartupState.READY
        assert not svc.should_block_message("hello")
        assert not svc.should_block_message("/help")

    def test_run_async_calls_on_ready(self):
        container = _make_container()

        # Patch the long-running stages so they complete instantly
        with patch.object(StartupService, "_connect_ollama", lambda self: self.profile.stop_stage("Ollama Connection")), \
             patch.object(StartupService, "_warmup_model", lambda self: self.profile.stop_stage("Model Warm-Up")):

            ready_event = threading.Event()
            svc = StartupService(container)

            # Remove all pre-started stage timers so stop_stage won't fail
            svc.run_async(
                on_ready=lambda: ready_event.set(),
                on_error=lambda e: None,
            )
            completed = ready_event.wait(timeout=10)

        assert completed, "on_ready callback was not called"
        assert svc.state == StartupState.READY
        assert svc.is_ready

    def test_profile_records_stages_after_completion(self):
        container = _make_container()

        with patch.object(StartupService, "_connect_ollama", lambda self: self.profile.stop_stage("Ollama Connection")), \
             patch.object(StartupService, "_warmup_model", lambda self: self.profile.stop_stage("Model Warm-Up")):

            done = threading.Event()
            svc = StartupService(container)
            svc.run_async(on_ready=lambda: done.set(), on_error=lambda e: done.set())
            done.wait(timeout=10)

        # At minimum SessionContext and Scheduler should have been recorded
        assert "SessionContext" in svc.profile.stages
        assert "Scheduler" in svc.profile.stages
        assert svc.profile.total_time > 0
