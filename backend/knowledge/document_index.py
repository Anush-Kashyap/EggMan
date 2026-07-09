from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from backend.knowledge.chunker import Chunker, TextChunk
from backend.knowledge.document_parser import DocumentParser, ParsedDocument
from backend.knowledge.embedding_service import EmbeddingService
from backend.knowledge.vector_store import VectorStore

logger = logging.getLogger("eggman")


@dataclass(slots=True)
class IndexingReport:
    doc_id: int
    filename: str
    status: str  # success, failed
    chunk_count: int = 0
    embedding_count: int = 0
    parse_duration_ms: float = 0.0
    chunk_duration_ms: float = 0.0
    embed_duration_ms: float = 0.0
    store_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    error: str = ""

    def __str__(self) -> str:
        return (
            f"IndexingReport(doc_id={self.doc_id}, filename={self.filename}, "
            f"status={self.status}, chunks={self.chunk_count}, "
            f"total_ms={self.total_duration_ms:.0f})"
        )


ProgressCallback = Callable[[int, str], None]
"""Callback(doc_id, status_string)"""


class DocumentIndex:
    """Background indexing pipeline: parse, chunk, embed, store."""

    def __init__(
        self,
        document_parser: DocumentParser,
        chunker: Chunker,
        embedding_service: EmbeddingService,
        vector_store: VectorStore,
    ) -> None:
        self._document_parser = document_parser
        self._chunker = chunker
        self._embedding_service = embedding_service
        self._vector_store = vector_store
        self._progress_callbacks: List[ProgressCallback] = []

    def on_progress(self, callback: ProgressCallback) -> None:
        self._progress_callbacks.append(callback)

    def _notify_progress(self, doc_id: int, status: str) -> None:
        for cb in self._progress_callbacks:
            try:
                cb(doc_id, status)
            except Exception:
                logger.exception("Progress callback failed")

    def index_document_sync(
        self,
        doc_id: int,
        file_path: Path,
        filename: str,
    ) -> IndexingReport:
        """Run the full indexing pipeline synchronously. Call from background thread."""
        report = IndexingReport(doc_id=doc_id, filename=filename, status="failed")
        t_start = time.perf_counter()

        try:
            # Stage 1: Parse
            self._notify_progress(doc_id, "parsing")
            t0 = time.perf_counter()
            parsed: ParsedDocument = self._document_parser.parse(file_path)
            report.parse_duration_ms = (time.perf_counter() - t0) * 1000
            logger.info(
                "Index: parsed doc_id=%s pages=%d chars=%d",
                doc_id,
                parsed.total_pages,
                len(parsed.full_text),
            )

            # Stage 2: Chunk
            self._notify_progress(doc_id, "chunking")
            t1 = time.perf_counter()
            chunks: List[TextChunk] = self._chunker.chunk(parsed, doc_id)
            report.chunk_duration_ms = (time.perf_counter() - t1) * 1000
            report.chunk_count = len(chunks)
            logger.info("Index: chunked doc_id=%s into %d chunks", doc_id, len(chunks))

            # Stage 3: Embed
            if not chunks:
                raise RuntimeError("No chunks generated from document")

            self._notify_progress(doc_id, "embedding")
            t2 = time.perf_counter()
            texts = [c.text for c in chunks]
            embeddings = self._embedding_service.embed_batch(texts)
            report.embed_duration_ms = (time.perf_counter() - t2) * 1000
            report.embedding_count = len(embeddings)
            logger.info(
                "Index: embedded doc_id=%s chunks=%d embed_ms=%.1f",
                doc_id,
                len(embeddings),
                report.embed_duration_ms,
            )

            # Stage 4: Store
            t3 = time.perf_counter()
            self._vector_store.store_chunks(
                chunks,
                embeddings,
                model_name=self._embedding_service.model_name(),
            )
            report.store_duration_ms = (time.perf_counter() - t3) * 1000

            report.status = "success"
            report.total_duration_ms = (time.perf_counter() - t_start) * 1000

            logger.info(
                "Index: completed doc_id=%s status=success chunks=%d total_ms=%.0f",
                doc_id,
                report.chunk_count,
                report.total_duration_ms,
            )

        except Exception as exc:
            report.status = "failed"
            report.error = str(exc)
            report.total_duration_ms = (time.perf_counter() - t_start) * 1000
            logger.error(
                "Index: failed doc_id=%s error=%s total_ms=%.0f",
                doc_id,
                exc,
                report.total_duration_ms,
            )

        self._notify_progress(doc_id, report.status)
        return report

    def index_document_async(
        self,
        doc_id: int,
        file_path: Path,
        filename: str,
    ) -> threading.Thread:
        """Start indexing in a background daemon thread. Returns the thread."""
        thread = threading.Thread(
            target=self.index_document_sync,
            args=(doc_id, file_path, filename),
            daemon=True,
        )
        thread.start()
        return thread
