from __future__ import annotations

import time
import pytest
from backend.profiler.performance_profiler import PerformanceProfiler
from backend.session.session_manager import SessionManager


def test_profiler_dev_mode_deactivated():
    """Verify that if Developer Mode is disabled, the profiler doesn't track request info."""
    SessionManager.get_instance().context.developer_mode = False
    profiler = PerformanceProfiler.get_instance()
    
    profile = profiler.start_request("Test user prompt")
    assert profile is None
    assert profiler.get_current_profile() is None


def test_profiler_dev_mode_activated():
    """Verify that if Developer Mode is active, the profiler tracks requests, stages, and appends to history."""
    SessionManager.get_instance().context.developer_mode = True
    profiler = PerformanceProfiler.get_instance()
    
    # Reset counter and history for predictability
    profiler.history.clear()
    profiler._counter = 0

    profile = profiler.start_request("Test query")
    assert profile is not None
    assert profile.request_num == 1
    assert profile.user_message == "Test query"
    assert profiler.get_current_profile() is profile

    # Track stages
    profiler.start_stage("Prompt Builder")
    time.sleep(0.01)
    profiler.stop_stage("Prompt Builder")
    
    assert "Prompt Builder" in profile.stages
    assert profile.stages["Prompt Builder"] > 0.0
    
    # Finalize request
    profiler.finalize_request(
        model_name="qwen3:8b",
        memory_used=True,
        knowledge_used=False,
        vision_used=False,
        tools_executed=True
    )
    
    assert len(profiler.history) == 1
    stored = profiler.history[0]
    assert stored.model_name == "qwen3:8b"
    assert stored.memory_used is True
    assert stored.tools_executed is True
    assert stored.total_time > 0.0
    assert profiler.get_current_profile() is None


def test_gpu_diagnostics_failsafe():
    """Verify that GPU diagnostic call executes safely without exceptions."""
    profiler = PerformanceProfiler.get_instance()
    gpu_name, vram = profiler.get_gpu_diagnostics()
    assert isinstance(gpu_name, str)
    assert isinstance(vram, str)
