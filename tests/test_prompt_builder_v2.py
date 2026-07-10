from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from backend.prompt.prompt_context import PromptContext
from backend.prompt.prompt_registry import PromptRegistry
from backend.prompt.prompt_cache import PromptCache
from backend.prompt.prompt_builder import PromptBuilder, PromptStats


def test_registry_discovery():
    """Verify that all core modules register successfully."""
    modules = PromptRegistry.get_modules()
    names = {m.name() for m in modules}
    expected = {"identity", "persona", "communication", "memory", "knowledge", "vision", "tools", "scheduler", "developer"}
    assert expected.issubset(names)


def test_context_applicability():
    """Verify that applicability flags match request contexts."""
    # Context with vision/image
    ctx1 = PromptContext(has_image=True)
    vision_mod = PromptRegistry.get("vision")
    assert vision_mod.is_applicable(ctx1) is True

    # Context without vision/image
    ctx2 = PromptContext(has_image=False)
    assert vision_mod.is_applicable(ctx2) is False


def test_cache_hits_and_misses():
    """Verify caching behavior for static vs dynamic modules."""
    cache = PromptCache()
    
    # Static cached mock key
    assert cache.get("test_key") is None
    assert cache.misses == 1
    
    cache.set("test_key", "cached content")
    assert cache.get("test_key") == "cached content"
    assert cache.hits == 1


def test_prompt_builder_stats():
    """Verify stats tracking on PromptBuilder."""
    pb = PromptBuilder()
    prompt = pb.build_system_prompt(
        mode="programming",
        is_voice=False,
        user_message="Verify code compilation",
    )
    
    stats = PromptBuilder.get_last_stats()
    assert stats is not None
    assert stats.total_tokens > 0
    assert stats.total_chars > 0
    assert "identity" in stats.modules_used
    assert "communication" in stats.modules_used
    assert stats.build_duration_ms >= 0.0
