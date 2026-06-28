from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional

from backend.memory.memory_extractor import MemoryExtractor
from backend.memory.memory_repository import MemoryRepository
from backend.memory.models import MemoryCategory, MemoryRecord


class MemoryManager:
    """Coordinates memory extraction, storage, retrieval, updates, and deletion."""

    def __init__(
        self,
        repository: MemoryRepository,
        extractor: MemoryExtractor | None = None,
    ) -> None:
        self._repository = repository
        self._extractor = extractor or MemoryExtractor()
        self._logger = logging.getLogger("eggman")

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        existing = self._repository.find_memory(memory.key, memory.value)
        if existing is not None:
            existing.category = memory.category
            existing.importance = memory.importance
            existing.confidence = max(existing.confidence, memory.confidence)
            existing.last_accessed = datetime.now().isoformat(timespec="seconds")
            existing.access_count += 1
            saved = self._repository.update_memory(existing)
            self._logger.info("Memory stored id=%s key=%s action=updated", saved.id, saved.key)
            return saved

        saved = self._repository.save_memory(memory)
        self._logger.info("Memory stored id=%s key=%s action=created", saved.id, saved.key)
        return saved

    def update_memory(self, memory: MemoryRecord) -> MemoryRecord:
        return self._repository.update_memory(memory)

    def get_memory(self, memory_id: int) -> Optional[MemoryRecord]:
        return self._repository.get_memory(memory_id)

    def get_all_memories(self) -> List[MemoryRecord]:
        return self._repository.get_all_memories()

    def search_memories(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        return self._repository.search_memories(query, limit=limit)

    def semantic_search(self, query: str, limit: int = 5) -> List[MemoryRecord]:
        return self.retrieve_relevant_memories(query, limit=limit)

    def retrieve_relevant_memories(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        memories = self.get_all_memories()
        if len(memories) <= limit:
            selected = memories
        else:
            selected = self._rank_memories(query, memories)[:limit]

        self._repository.mark_accessed(selected)
        self._logger.info("Memory retrieved count=%d query=%r", len(selected), query)
        return selected

    def delete_memory(self, memory_id: int) -> None:
        self._repository.delete_memory(memory_id)

    def extract_and_store(self, user_message: str) -> Optional[MemoryRecord]:
        memory = self._extractor.extract(user_message)
        if memory is None:
            return None
        return self.save_memory(memory)

    def _rank_memories(self, query: str, memories: List[MemoryRecord]) -> List[MemoryRecord]:
        query_tokens = self._tokens(query)

        def score(memory: MemoryRecord) -> tuple[int, str]:
            memory_tokens = self._tokens(f"{memory.key} {memory.value} {memory.category.value}")
            overlap = len(query_tokens & memory_tokens)
            importance = {"high": 3, "medium": 2, "low": 1}.get(memory.importance.value, 1)
            recency = memory.updated_at or memory.created_at
            return (overlap * 10 + importance + min(memory.access_count, 5), recency)

        return sorted(memories, key=score, reverse=True)

    def _tokens(self, text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", text.lower()) if len(token) > 2}

    def categorize(self, content: str) -> str:
        lowered = content.lower()
        if any(token in lowered for token in ["favorite", "like", "love", "prefer"]):
            return MemoryCategory.PREFERENCE.value
        if any(token in lowered for token in ["birthday", "name", "relationship", "friend"]):
            return MemoryCategory.RELATIONSHIP.value
        if any(token in lowered for token in ["goal", "study", "major", "career"]):
            return MemoryCategory.SEMANTIC.value
        return MemoryCategory.WORKING.value
