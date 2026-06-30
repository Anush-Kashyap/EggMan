from __future__ import annotations

import logging
from pathlib import Path
from typing import List, Optional
import re

from backend.database.repositories.kb_repository import KBRepository
from backend.knowledge.document_manager import DocumentManager
from backend.knowledge.models import KBDocument

logger = logging.getLogger("eggman")


class KnowledgeManager:
    """Central manager for EggMan's Knowledge Base, coordinating document loading, indexing, and search."""

    def __init__(self, repository: KBRepository, document_manager: DocumentManager) -> None:
        self._repository = repository
        self._document_manager = document_manager

    def upload_document(self, file_path: Path) -> KBDocument:
        """Injest, process, index, and save the document to the persistent repository."""
        logger.info("KB: File uploaded: %s", file_path.name)
        
        # Determine file size
        file_size = file_path.stat().st_size
        
        # Load and process content (file processed)
        content = self._document_manager.ingest(file_path)
        logger.info("KB: File processed: %s, extracted %d chars", file_path.name, len(content))
        
        # File type
        file_type = file_path.suffix.lower().replace(".", "")
        
        # Save to database (file indexed)
        doc = self._repository.save_document(
            filename=file_path.name,
            file_type=file_type,
            file_size=file_size,
            content=content,
            source_path=str(file_path.absolute())
        )
        logger.info("KB: File indexed: ID=%s, filename=%s", doc.id, doc.filename)
        return doc

    def remove_document(self, doc_id: int) -> bool:
        """Remove a document from the persistent repository."""
        logger.info("KB: File removed requested: ID=%s", doc_id)
        success = self._repository.delete_document(doc_id)
        if success:
            logger.info("KB: File removed successfully: ID=%s", doc_id)
        else:
            logger.warning("KB: Failed to remove file: ID=%s not found", doc_id)
        return success

    def get_all_documents(self) -> List[KBDocument]:
        """Retrieve all registered documents in the Knowledge Base."""
        return self._repository.get_all_documents()

    def search(self, query: str, limit: int = 3) -> List[str]:
        """Search the Knowledge Base for relevant context passages or documents matching the query."""
        logger.info("KB: Retrieval performed: query='%s'", query)
        
        # Tokenize query into alphanumeric keywords
        keywords = re.findall(r"\w+", query.lower())
        if not keywords:
            logger.info("KB: Retrieval results: count=0 (empty query keywords)")
            return []
            
        docs = self._repository.search_documents(keywords, limit=limit)
        logger.info("KB: Retrieval results: count=%d", len(docs))
        
        results = []
        for doc in docs:
            # Reconstruct context block. In the future, we could return chunks,
            # but currently we return the relevant segment or full text.
            # Let's extract sentences or paragraphs containing some keywords to keep context concise.
            paragraphs = doc.content.split("\n")
            matched_paragraphs = []
            for p in paragraphs:
                p_clean = p.strip()
                if not p_clean:
                    continue
                # If paragraph matches any keyword, include it
                p_lower = p_clean.lower()
                if any(kw in p_lower for kw in keywords):
                    matched_paragraphs.append(p_clean)
            
            if matched_paragraphs:
                # Limit paragraphs per document to prevent context blowing up
                doc_context = "\n".join(matched_paragraphs[:8])
                results.append(f"--- Document: {doc.filename} ---\n{doc_context}")
            else:
                # Fallback to first part of document if no paragraph matched directly
                results.append(f"--- Document: {doc.filename} ---\n{doc.content[:1000]}")
                
        return results
