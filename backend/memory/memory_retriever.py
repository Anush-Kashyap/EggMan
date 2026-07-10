from __future__ import annotations

import logging
from backend.memory.models import MemoryRecord
from backend.memory.memory_repository import MemoryRepository
from backend.memory.memory_ranker import MemoryRanker
from backend.memory.memory_expiration import ExpirationManager

logger = logging.getLogger("eggman")


class MemoryRetriever:
    """Orchestrates memory retrieval, expiration checking, ranking, and filtering."""

    def __init__(
        self,
        repository: MemoryRepository,
        ranker: MemoryRanker,
        expiration_manager: ExpirationManager,
    ) -> None:
        self._repository = repository
        self._ranker = ranker
        self._expiration_manager = expiration_manager
        self._logger = logger

    def retrieve(self, query: str, limit: int = 10) -> list[MemoryRecord]:
        """Lazy expire, fetch active records, rank, and filter relevant memories."""
        # 1. Lazy expire temporary records
        self._expiration_manager.check_and_expire_lazy()

        # 2. Get active memories
        try:
            active_memories = [m for m in self._repository.get_all_memories() if getattr(m, "active", True)]
        except Exception as exc:
            self._logger.error("Failed to load active memories during retrieval: %s", exc)
            return []

        if not active_memories:
            return []

        # 3. Rank memories
        ranked = self._ranker.rank(query, active_memories)

        # 4. Filter by relevance (ensure there is at least one overlapping token, or it's a critical memory)
        query_tokens = self._ranker._tokenize(query)
        selected = []

        for m in ranked:
            mem_text = f"{m.key} {m.value} {m.category.value}"
            mem_tokens = self._ranker._tokenize(mem_text)
            overlap = len(query_tokens & mem_tokens)

            # Keep if there's keyword overlap OR if it's a high importance memory (>=80 importance)
            if overlap > 0 or getattr(m, "importance", 50) >= 80:
                selected.append(m)

        result = selected[:limit]
        self._logger.info("Memory retrieved count=%d query=%r", len(result), query)
        return result
