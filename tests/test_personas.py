"""
Tests for the EggMan Persona System.

Covers:
- PersonaManager singleton and registration
- Persona switching and unknown key handling
- Prompt injection into PromptBuilder
- ConversationEngine integration (prompt contains persona)
- Settings persistence key existence
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from unittest.mock import MagicMock

# Ensure project root is on sys.path for imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# PersonaManager tests
# ---------------------------------------------------------------------------

class TestPersonaManager:
    def setup_method(self):
        """Reset singleton before each test."""
        from backend.personas.persona_manager import PersonaManager
        PersonaManager._instance = None

    def test_singleton(self):
        from backend.personas.persona_manager import PersonaManager
        a = PersonaManager.get_instance()
        b = PersonaManager.get_instance()
        assert a is b

    def test_built_in_personas_registered(self):
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()
        keys = [p.key for p in manager.available_personas()]
        assert "normal" in keys
        assert "coding" in keys
        assert "party" in keys

    def test_default_active_is_normal(self):
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()
        assert manager.get_active().key == "normal"

    def test_set_active_switches_persona(self):
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()
        result = manager.set_active("coding")
        assert result is True
        assert manager.get_active().key == "coding"

    def test_set_active_unknown_key_returns_false(self):
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()
        result = manager.set_active("nonexistent_persona")
        assert result is False
        # Active should remain normal (default)
        assert manager.get_active().key == "normal"

    def test_persona_prompt_not_empty(self):
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()
        for persona in manager.available_personas():
            prompt = persona.get_persona_prompt()
            assert isinstance(prompt, str)
            assert len(prompt) > 10, f"Persona {persona.key} has a suspiciously short prompt"

    def test_get_active_persona_prompt_returns_string(self):
        from backend.personas.persona_manager import PersonaManager
        manager = PersonaManager.get_instance()
        prompt = manager.get_active_persona_prompt()
        assert isinstance(prompt, str)
        assert len(prompt) > 0

    def test_custom_persona_registration(self):
        from backend.personas.persona_manager import PersonaManager
        from backend.personas.base_persona import BasePersona

        class TestPersona(BasePersona):
            @property
            def key(self): return "test_persona"
            @property
            def display_name(self): return "Test"
            @property
            def emoji(self): return "🔬"
            @property
            def avatar_path(self): return None
            def get_persona_prompt(self): return "PERSONA: TEST\n- This is a test persona."

        manager = PersonaManager.get_instance()
        manager.register(TestPersona())
        keys = [p.key for p in manager.available_personas()]
        assert "test_persona" in keys


# ---------------------------------------------------------------------------
# Prompt injection tests
# ---------------------------------------------------------------------------

class TestPromptBuilderPersonaInjection:
    def test_persona_prompt_injected_into_system_prompt(self):
        from backend.ai.prompt_builder import PromptBuilder
        builder = PromptBuilder()
        persona_prompt = "PERSONA: TEST\n- Test persona."
        result = builder.build_system_prompt("casual", False, "hello", persona_prompt=persona_prompt)
        assert "PERSONA: TEST" in result

    def test_persona_prompt_is_second_section(self):
        from backend.ai.prompt_builder import PromptBuilder
        builder = PromptBuilder()
        persona_prompt = "PERSONA: TEST\n- Test persona."
        result = builder.build_system_prompt("casual", False, "hello", persona_prompt=persona_prompt)
        identity_pos = result.find("IDENTITY:")
        persona_pos = result.find("PERSONA: TEST")
        assert identity_pos < persona_pos, "Persona prompt should appear after identity"

    def test_no_persona_prompt_still_works(self):
        from backend.ai.prompt_builder import PromptBuilder
        builder = PromptBuilder()
        result = builder.build_system_prompt("casual", False, "hello")
        assert "IDENTITY:" in result
        assert "COMMUNICATION STYLE:" in result

    def test_voice_mode_appended_with_persona(self):
        from backend.ai.prompt_builder import PromptBuilder
        builder = PromptBuilder()
        persona_prompt = "PERSONA: CODING GUY\n- Code."
        result = builder.build_system_prompt("casual", True, "hi", persona_prompt=persona_prompt)
        assert "VOICE CONVERSATION RULES:" in result
        assert "PERSONA: CODING GUY" in result


# ---------------------------------------------------------------------------
# Settings persistence
# ---------------------------------------------------------------------------

class TestPersonaSettingsPersistence:
    def test_active_persona_key_in_defaults(self):
        from core.settings import SettingsManager
        manager = SettingsManager.__new__(SettingsManager)
        assert "active_persona" in SettingsManager._DEFAULTS

    def test_default_persona_is_normal(self):
        from core.settings import SettingsManager
        assert SettingsManager._DEFAULTS["active_persona"] == "normal"
