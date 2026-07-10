from __future__ import annotations

import logging
from backend.memory.models import MemoryCategory

logger = logging.getLogger("eggman")


class MemoryClassifier:
    """Classifies memory content into one of the MemoryCategory enums."""

    def __init__(self) -> None:
        self._logger = logger

    def classify(self, content: str) -> MemoryCategory:
        """Categorize the content based on keywords and patterns."""
        lowered = content.lower()

        # Temporary cues
        if any(w in lowered for w in ["today", "tonight", "this week", "this weekend", "temporary", "sick", "travelling", "busy now", "currently"]):
            return MemoryCategory.TEMPORARY

        # Preference cues
        if any(w in lowered for w in ["favorite", "like", "love", "prefer", "dislike", "hate", "preferred"]):
            return MemoryCategory.PREFERENCE

        # Goal cues
        if any(w in lowered for w in ["want to", "wish to", "goal", "hope to", "plan to", "aim to", "target"]):
            return MemoryCategory.GOAL

        # Skill cues
        if any(w in lowered for w in ["know how to", "know ", "learned", "learning", "skill", "expert in", "fluent in"]):
            return MemoryCategory.SKILL

        # Project cues
        if any(w in lowered for w in ["building", "making", "developing", "project", "portfolio", "codebase", "eggman"]):
            return MemoryCategory.PROJECT

        # Habit cues
        if any(w in lowered for w in ["usually", "always", "every morning", "every day", "normally", "often", "seldom", "routine"]):
            return MemoryCategory.HABIT

        # Personal Fact cues
        if any(w in lowered for w in ["birthday", "born", "live in", "from", "age is", "my name", "call me"]):
            return MemoryCategory.PERSONAL_FACT

        # Default fallback
        return MemoryCategory.PERMANENT
