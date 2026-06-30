from __future__ import annotations

import pytest
from backend.ai.prompt_builder import PromptBuilder
from core.conversation import ConversationEngine


def test_prompt_builder_assembling():
    """Verify that PromptBuilder correctly structures prompts, appends voice rules, and handles intent/length constraints."""
    pb = PromptBuilder()
    
    # 1. Casual mode system prompt with a direct greeting to trigger the constraint
    prompt_casual = pb.build_system_prompt(mode="casual", is_voice=False, user_message="hello")
    assert "IDENTITY" in prompt_casual
    assert "PERSONALITY" in prompt_casual
    assert "COMMUNICATION STYLE" in prompt_casual
    assert "CONVERSATION RULES" in prompt_casual
    assert "MEMORY RULES" in prompt_casual
    assert "RESPONSE LENGTH CONSTRAINT" in prompt_casual
    assert "CONVERSATION MODE: CASUAL" in prompt_casual
    assert "VOICE" not in prompt_casual  # Not voice mode
    
    # 2. Programming mode + voice mode prompt
    prompt_prog_voice = pb.build_system_prompt(mode="programming", is_voice=True, user_message="Fix this code error please")
    assert "CONVERSATION MODE: PROGRAMMING" in prompt_prog_voice
    assert "VOICE CONVERSATION RULES" in prompt_prog_voice
    assert "RESPONSE LENGTH CONSTRAINT" not in prompt_prog_voice  # Not a greeting/small talk


def test_conversation_engine_mode_detection():
    """Test ConversationEngine's intent detection logic (programming, teaching, casual)."""
    engine = ConversationEngine(ai_engine=None)
    
    # Programming cues
    assert engine._detect_mode("What does this code compile to?") == "programming"
    assert engine._detect_mode("I got an IndexOutOfBoundsException in python") == "programming"
    
    # Teaching cues
    assert engine._detect_mode("Can you explain how does recursion work?") == "teaching"
    assert engine._detect_mode("What is the difference between TCP and UDP?") == "teaching"
    
    # Casual cues
    assert engine._detect_mode("How's your day going?") == "casual"
    assert engine._detect_mode("Let's talk about music.") == "casual"
