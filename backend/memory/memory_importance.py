from __future__ import annotations

import logging
from backend.memory.models import MemoryCategory

logger = logging.getLogger("eggman")


class ImportanceScorer:
    """Computes a numeric importance score between 0 and 100 for a memory."""

    def __init__(self) -> None:
        self._logger = logger

    def score(self, category: MemoryCategory, key: str, value: str, source: str) -> int:
        """Calculate the importance score based on multiple heuristics."""
        # 1. Base score by category
        base_scores = {
            MemoryCategory.PERSONAL_FACT: 70,
            MemoryCategory.GOAL: 65,
            MemoryCategory.PREFERENCE: 55,
            MemoryCategory.PROJECT: 50,
            MemoryCategory.SKILL: 45,
            MemoryCategory.PERMANENT: 40,
            MemoryCategory.HABIT: 35,
            MemoryCategory.TEMPORARY: 20,
        }
        
        score = base_scores.get(category, 40)

        # 2. Explicitness/Source bonus
        if source == "explicit":
            score += 15
        elif source == "remembered":
            score += 10

        # 3. Emphasis keywords (e.g., 'always', 'never', 'important', 'crucial')
        lowered_val = value.lower()
        if any(w in lowered_val for w in ["always", "never", "forever", "must", "important", "crucial", "essential"]):
            score += 10

        # 4. Limit range
        return max(0, min(100, score))
