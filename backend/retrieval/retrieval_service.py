from __future__ import annotations

from typing import List

from backend.memory.memory_manager import MemoryManager
from backend.memory.models import MemoryRecord


class RetrievalService:
    """Retrieves relevant memories for later prompt augmentation."""

    def __init__(
        self,
        memory_manager: MemoryManager | None = None,
        embedding_service: object | None = None,
        vector_store: object | None = None,
    ) -> None:
        self._memory_manager = memory_manager

    def retrieve(self, user_message: str, limit: int = 10) -> List[MemoryRecord]:
        if self._memory_manager is None:
            return []

        return self._memory_manager.retrieve_relevant_memories(user_message, limit=limit)
