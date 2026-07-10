from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import List, Optional

from backend.database.repositories.kb_repository import KBRepository
from backend.knowledge.document_index import DocumentIndex, IndexingReport
from backend.knowledge.document_manager import DocumentManager
from backend.knowledge.models import KBDocument
from backend.knowledge.retriever import Retriever
from backend.knowledge.vector_store import VectorStore

logger = logging.getLogger("eggman")


from backend.registry.capability.decorators import capability

@capability(
    id="knowledge",
    name="Knowledge",
    description="Indexes and searches uploaded PDF documentation.",
    category="general",
    version="1.0.0"
)
class KnowledgeManager:
    """Public interface for the Knowledge System.

    Coordinates indexing, retrieval, and document management.
    ConversationEngine communicates ONLY with this class.
    """

    def __init__(
        self,
        repository: KBRepository,
        document_manager: DocumentManager,
        document_index: Optional[DocumentIndex] = None,
        retriever: Optional[Retriever] = None,
        vector_store: Optional[VectorStore] = None,
    ) -> None:
        self._repository = repository
        self._document_manager = document_manager
        self._document_index = document_index
        self._retriever = retriever
        self._vector_store = vector_store
        self._indexing_lock = threading.Lock()
        self._last_report: Optional[IndexingReport] = None

    @property
    def last_report(self) -> Optional[IndexingReport]:
        return self._last_report

    def upload_document(self, file_path: Path) -> KBDocument:
        """Upload a document and start background indexing.

        1. Store metadata (status=waiting) in eggman.db
        2. Start background indexing (parse, chunk, embed, store)
        3. Return immediately with the document stub
        """
        logger.info("KM: upload_document called for %s", file_path.name)

        file_size = file_path.stat().st_size
        file_type = file_path.suffix.lower().replace(".", "")

        doc = self._repository.save_document(
            filename=file_path.name,
            file_type=file_type,
            file_size=file_size,
            content="",
            source_path=str(file_path.absolute()),
            metadata_dict={"status": "waiting"},
        )
        logger.info("KM: document metadata saved id=%s filename=%s", doc.id, doc.filename)

        if self._document_index is not None:
            self._start_background_indexing(doc, file_path)
        else:
            # Legacy mode: index synchronously via document manager
            try:
                content = self._document_manager.ingest(file_path)
                self._repository.update_content(doc.id, content)
                self._repository.update_status(doc.id, "indexed")
                logger.info("KM: legacy indexing completed for id=%s", doc.id)
            except Exception as exc:
                self._repository.update_status(doc.id, "failed")
                logger.error("KM: legacy indexing failed id=%s error=%s", doc.id, exc)

        return doc

    def _start_background_indexing(self, doc: KBDocument, file_path: Path) -> None:
        """Launch background indexing thread."""

        def _on_progress(doc_id: int, status: str) -> None:
            self._repository.update_status(doc_id, status)
            logger.debug("KM: progress doc_id=%s status=%s", doc_id, status)

        def _index_worker() -> None:
            try:
                self._document_index.on_progress(_on_progress)
                report = self._document_index.index_document_sync(
                    doc_id=doc.id,
                    file_path=file_path,
                    filename=doc.filename,
                )
                with self._indexing_lock:
                    self._last_report = report

                if report.status == "success":
                    self._repository.update_status(doc.id, "indexed")
                    self._repository.update_chunk_count(doc.id, report.chunk_count)
                else:
                    self._repository.update_status(doc.id, "failed")

                logger.info(
                    "KM: background indexing finished doc_id=%s status=%s chunks=%d total_ms=%.0f",
                    doc.id,
                    report.status,
                    report.chunk_count,
                    report.total_duration_ms,
                )
            except Exception as exc:
                self._repository.update_status(doc.id, "failed")
                logger.exception("KM: background indexing crashed doc_id=%s error=%s", doc.id, exc)

        thread = threading.Thread(target=_index_worker, daemon=True)
        thread.start()
        logger.info("KM: background indexing thread started for doc_id=%s", doc.id)

    def remove_document(self, doc_id: int) -> bool:
        """Remove a document from both databases."""
        logger.info("KM: remove_document requested id=%s", doc_id)
        if self._vector_store is not None:
            try:
                self._vector_store.delete_document(doc_id)
            except Exception as exc:
                logger.error("KM: vector store delete failed id=%s error=%s", doc_id, exc)

        success = self._repository.delete_document(doc_id)
        if success:
            logger.info("KM: document removed id=%s", doc_id)
        else:
            logger.warning("KM: document not found id=%s", doc_id)
        return success

    def get_all_documents(self) -> List[KBDocument]:
        """Retrieve all registered documents with current status."""
        return self._repository.get_all_documents()

    def get_document_by_id(self, doc_id: int) -> Optional[KBDocument]:
        return self._repository.get_document_by_id(doc_id)

    def search(self, query: str, limit: int = 5) -> List[str]:
        """Semantic search. Returns formatted context strings for prompt injection.

        Falls back to keyword search if retriever is not available.
        """
        if self._retriever is not None:
            return self._semantic_search(query, limit)
        return self._keyword_search(query, limit)

    def _semantic_search(self, query: str, limit: int) -> List[str]:
        """Perform semantic retrieval and format results for injection."""
        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        profiler.start_stage("Knowledge Retrieval")

        try:
            stats = self._retriever.retrieve(query, top_k=limit)
            results = stats.results

            if not results:
                return []

            # Build document-name cache
            doc_names: dict[int, str] = {}
            for r in results:
                if r.chunk.document_id not in doc_names:
                    doc = self._repository.get_document_by_id(r.chunk.document_id)
                    doc_names[r.chunk.document_id] = doc.filename if doc else f"doc_{r.chunk.document_id}"

            formatted: List[str] = []
            current_doc: Optional[int] = None
            doc_sections: List[str] = []

            for r in results:
                name = doc_names.get(r.chunk.document_id, f"doc_{r.chunk.document_id}")
                if r.chunk.document_id != current_doc:
                    if doc_sections:
                        formatted.append(f"--- Document: {doc_names.get(current_doc or 0, '')} ---\n" + "\n".join(doc_sections))
                    current_doc = r.chunk.document_id
                    doc_sections = []

                page_info = f" [Page {r.chunk.page_number}]" if r.chunk.page_number is not None else ""
                doc_sections.append(f"{page_info}: {r.chunk.text}")

            if doc_sections and current_doc is not None:
                formatted.append(f"--- Document: {doc_names.get(current_doc, '')} ---\n" + "\n".join(doc_sections))

            # Developer Mode logging
            from backend.session.session_manager import SessionManager
            try:
                session = SessionManager.get_instance().context
                if session.developer_mode:
                    logger.info("[DEV MODE] Knowledge retrieval: query='%s'", query)
                    logger.info("[DEV MODE] Retrieval results: %d chunks", len(results))
                    logger.info("[DEV MODE] Retrieval duration: embed_ms=%.1f search_ms=%.1f",
                        stats.embedding_duration_ms, stats.search_duration_ms)
                    for r in results:
                        logger.info("[DEV MODE]   Chunk #%s (doc=%s, score=%.3f): %s...",
                            r.chunk.chunk_index, r.chunk.document_id, r.score, r.chunk.text[:60])
            except Exception:
                pass

            return formatted

        finally:
            profiler.stop_stage("Knowledge Retrieval")

    def _keyword_search(self, query: str, limit: int) -> List[str]:
        """Fallback keyword-based search."""
        import re
        keywords = re.findall(r"\w+", query.lower())
        if not keywords:
            return []

        docs = self._repository.search_documents(keywords, limit=limit)
        results = []
        for doc in docs:
            paragraphs = doc.content.split("\n")
            matched = [p.strip() for p in paragraphs if p.strip() and any(kw in p.lower() for kw in keywords)]
            if matched:
                results.append(f"--- Document: {doc.filename} ---\n" + "\n".join(matched[:8]))
            else:
                results.append(f"--- Document: {doc.filename} ---\n{doc.content[:1000]}")
        return results

    def is_retrieval_ready(self) -> bool:
        """Check whether semantic retrieval is available (indexed documents exist)."""
        if self._retriever is None:
            return False
        if self._vector_store is None:
            return False
        return self._vector_store.get_vector_count() > 0
