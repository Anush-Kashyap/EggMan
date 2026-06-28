from __future__ import annotations

from typing import List

from backend.memory.memory_manager import MemoryManager
from backend.memory.models import MemoryCategory, MemoryRecord


class MemoryService:
    """Application-facing facade for memory operations."""

    def __init__(self, memory_manager: MemoryManager) -> None:
        self._memory_manager = memory_manager

    def remember(self, content: str, category: str | None = None, metadata: dict | None = None) -> MemoryRecord:
        memory = MemoryRecord(
            category=MemoryCategory(self._memory_manager.categorize(content) if category is None else category),
            key="note",
            value=content,
            metadata=metadata or {},
        )
        return self._memory_manager.save_memory(memory)

    def recall(self, category: str | None = None, limit: int = 5) -> List[MemoryRecord]:
        if category is None:
            return self._memory_manager.get_all_memories()[:limit]
        return [memory for memory in self._memory_manager.get_all_memories() if memory.category.value == category][:limit]
