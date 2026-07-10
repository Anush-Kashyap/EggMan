from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import List, Optional, Any

from backend.memory.memory_extractor import MemoryExtractor
from backend.memory.memory_repository import MemoryRepository
from backend.memory.models import MemoryCategory, MemoryRecord
from backend.memory.memory_classifier import MemoryClassifier
from backend.memory.memory_importance import ImportanceScorer
from backend.memory.memory_conflict_resolver import ConflictResolver
from backend.memory.memory_retriever import MemoryRetriever


class MemoryManager:
    """Coordinates memory extraction, classification, scoring, storage, updates, and retrieval."""

    def __init__(
        self,
        repository: MemoryRepository,
        extractor: MemoryExtractor | None = None,
        classifier: MemoryClassifier | None = None,
        importance_scorer: ImportanceScorer | None = None,
        conflict_resolver: ConflictResolver | None = None,
        retriever: MemoryRetriever | None = None,
    ) -> None:
        self._repository = repository
        self._extractor = extractor or MemoryExtractor()
        self._classifier = classifier or MemoryClassifier()
        self._importance_scorer = importance_scorer or ImportanceScorer()
        self._conflict_resolver = conflict_resolver or ConflictResolver(repository)

        if retriever is None:
            from backend.memory.memory_expiration import ExpirationManager
            from backend.memory.memory_ranker import MemoryRanker
            exp_mgr = ExpirationManager(repository)
            ranker = MemoryRanker()
            self._retriever = MemoryRetriever(repository, ranker, exp_mgr)
        else:
            self._retriever = retriever

        self._logger = logging.getLogger("eggman")

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        """Run through importance scoring and conflict resolution before saving."""
        # 1. Classify if category is default semantic/working
        if memory.category in (MemoryCategory.SEMANTIC, MemoryCategory.WORKING, MemoryCategory.PERMANENT):
            memory.category = self._classifier.classify(memory.value)

        # 2. Score importance
        memory.importance = self._importance_scorer.score(
            memory.category, memory.key, memory.value, memory.source
        )

        # 3. Resolve conflicts
        self._conflict_resolver.resolve(memory)

        # 4. Handle expiration if temporary
        if memory.category == MemoryCategory.TEMPORARY:
            self._retriever._expiration_manager.set_expiration(memory)

        # 5. Persist
        existing = self._repository.find_memory(memory.key, memory.value)
        if existing is not None:
            existing.category = memory.category
            existing.importance = memory.importance
            existing.confidence = max(existing.confidence, memory.confidence)
            existing.last_accessed = datetime.now().isoformat(timespec="seconds")
            existing.access_count += 1
            existing.active = memory.active
            existing.supersedes = memory.supersedes
            existing.expires_at = memory.expires_at
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
        """Core retrieval endpoint utilizing Expiration, Ranking, and Filtering."""
        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        
        t_start = datetime.now()
        memories = self._retriever.retrieve(query, limit=limit)
        duration_ms = (datetime.now() - t_start).total_seconds() * 1000

        # Mark last accessed
        self._repository.mark_accessed(memories)

        # Log diagnostic timing
        self._logger.info(
            "Memory retrieval took %.2fms, retrieved %d records",
            duration_ms,
            len(memories),
        )
        return memories

    def delete_memory(self, memory_id: int) -> None:
        self._repository.delete_memory(memory_id)

    def extract_and_store(self, user_message: str) -> Optional[MemoryRecord]:
        """Extract a memory from a user message and store it using the full pipeline."""
        memory = self._extractor.extract(user_message)
        if memory is None:
            return None
        return self.save_memory(memory)

    def categorize(self, content: str) -> str:
        """Classify content. Retained for backwards compatibility."""
        return self._classifier.classify(content).value

    def get_memory_stats(self) -> dict[str, Any]:
        """Gather memory system analytics for Egg Inspector."""
        try:
            memories = self.get_all_memories()
        except Exception:
            memories = []

        total = len(memories)
        active = sum(1 for m in memories if getattr(m, "active", True))
        expired = sum(1 for m in memories if not getattr(m, "active", True) and getattr(m, "expires_at", None))
        superseded = sum(1 for m in memories if getattr(m, "supersedes", None) is not None)

        # Categories
        categories = {}
        for m in memories:
            cat_name = m.category.value
            categories[cat_name] = categories.get(cat_name, 0) + 1

        # Importance
        importances = {
            "Very Low (0-20)": 0,
            "Low (21-40)": 0,
            "Medium (41-60)": 0,
            "High (61-80)": 0,
            "Critical (81-100)": 0,
        }
        for m in memories:
            imp = getattr(m, "importance", 50)
            if imp <= 20:
                importances["Very Low (0-20)"] += 1
            elif imp <= 40:
                importances["Low (21-40)"] += 1
            elif imp <= 60:
                importances["Medium (41-60)"] += 1
            elif imp <= 80:
                importances["High (61-80)"] += 1
            else:
                importances["Critical (81-100)"] += 1

        # Avg Confidence
        avg_conf = sum(getattr(m, "confidence", 0.0) for m in memories) / max(1, total)

        # Database size
        try:
            db_path = self._repository._database_manager.database_path
            db_size = db_path.stat().st_size if db_path.exists() else 0
        except Exception:
            db_size = 0

        return {
            "total_memories": total,
            "active_memories": active,
            "expired_memories": expired,
            "superseded_memories": superseded,
            "category_distribution": categories,
            "importance_distribution": importances,
            "average_confidence": avg_conf,
            "db_size_bytes": db_size,
        }
