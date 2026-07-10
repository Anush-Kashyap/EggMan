from __future__ import annotations

import logging
import re
from datetime import datetime
from backend.memory.models import MemoryCategory, MemoryRecord

logger = logging.getLogger("eggman")


class MemoryRanker:
    """Ranks memories using a multi-factor score (relevance, importance, recency, confidence)."""

    def __init__(self) -> None:
        self._logger = logger

    def rank(self, query: str, memories: list[MemoryRecord]) -> list[MemoryRecord]:
        """Rank a list of memories against a query and return them sorted by score descending."""
        if not memories:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            # If query is empty or has no significant tokens, rank by importance and recency
            return sorted(memories, key=lambda m: (m.importance, m.updated_at or m.created_at), reverse=True)

        scored_memories = []
        now = datetime.now()

        for m in memories:
            # 1. Relevance: token overlap (Jaccard-like or token match score)
            mem_text = f"{m.key} {m.value} {m.category.value}"
            mem_tokens = self._tokenize(mem_text)
            overlap = len(query_tokens & mem_tokens)
            
            # Normalize relevance to 0.0 - 1.0 range
            relevance_score = min(1.0, overlap / max(1, len(query_tokens)))

            # 2. Importance: 0-100 normalized to 0.0 - 1.0
            importance_score = getattr(m, "importance", 50) / 100.0

            # 3. Recency: time decay factor
            recency_score = 0.5  # default
            time_str = m.updated_at or m.created_at
            if time_str:
                try:
                    dt = datetime.fromisoformat(time_str)
                    days_diff = max(0, (now - dt).days)
                    # Exponential decay over days (half life of 7 days)
                    recency_score = 2.0 ** (-days_diff / 7.0)
                except ValueError:
                    pass

            # 4. Confidence: 0.0 - 1.0
            confidence_score = getattr(m, "confidence", 0.0)

            # 5. Category boost
            category_boost = 0.0
            if m.category in (MemoryCategory.PREFERENCE, MemoryCategory.GOAL, MemoryCategory.PERSONAL_FACT):
                category_boost = 0.15

            # Combined score: weights must sum up or balance
            # relevance (40%), importance (30%), recency (15%), confidence (10%), category boost (5%)
            total_score = (
                (relevance_score * 0.40) +
                (importance_score * 0.30) +
                (recency_score * 0.15) +
                (confidence_score * 0.10) +
                (category_boost * 0.05)
            )

            # Store the computed score in metadata temporarily so it can be inspected
            m.metadata["ranking_score"] = total_score
            scored_memories.append((total_score, m))

        # Sort descending by score
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [item[1] for item in scored_memories]

    def _tokenize(self, text: str) -> set[str]:
        """Convert text to lowercase alphanumeric tokens of length > 2."""
        return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2}
