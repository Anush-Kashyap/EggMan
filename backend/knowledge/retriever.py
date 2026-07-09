from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from backend.knowledge.embedding_service import EmbeddingService
from backend.knowledge.vector_store import SearchResult, VectorStore

logger = logging.getLogger("eggman")


@dataclass(slots=True)
class RetrievalStats:
    query: str = ""
    embedding_duration_ms: float = 0.0
    search_duration_ms: float = 0.0
    top_k: int = 5
    results: List[SearchResult] = field(default_factory=list)
    average_score: float = 0.0


class Retriever:
    """Performs semantic retrieval: embed query, search vector store, return Top-K chunks."""

    def __init__(
        self,
        vector_store: VectorStore,
        embedding_service: EmbeddingService,
        top_k: int = 5,
    ) -> None:
        self._vector_store = vector_store
        self._embedding_service = embedding_service
        self._top_k = top_k
        self._last_stats: Optional[RetrievalStats] = None

    @property
    def top_k(self) -> int:
        return self._top_k

    @top_k.setter
    def top_k(self, value: int) -> None:
        self._top_k = value

    @property
    def last_stats(self) -> Optional[RetrievalStats]:
        return self._last_stats

    def retrieve(self, query: str, top_k: Optional[int] = None) -> RetrievalStats:
        import time

        stats = RetrievalStats(query=query)
        k = top_k or self._top_k

        t0 = time.perf_counter()
        query_embedding = self._embedding_service.embed(query)
        stats.embedding_duration_ms = (time.perf_counter() - t0) * 1000

        t1 = time.perf_counter()
        results = self._vector_store.search(query_embedding, top_k=k)
        stats.search_duration_ms = (time.perf_counter() - t1) * 1000

        stats.results = results
        stats.top_k = k
        if results:
            stats.average_score = sum(r.score for r in results) / len(results)

        self._last_stats = stats

        logger.debug(
            "Retriever query='%s' top_k=%d results=%d embed_ms=%.1f search_ms=%.1f avg_score=%.3f",
            query[:50],
            k,
            len(results),
            stats.embedding_duration_ms,
            stats.search_duration_ms,
            stats.average_score,
        )
        return stats
