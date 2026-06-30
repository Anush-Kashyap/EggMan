from __future__ import annotations

import logging
import json
from datetime import datetime
from typing import List, Optional
from backend.database.database import DatabaseManager
from backend.knowledge.models import KBDocument

logger = logging.getLogger("eggman")


class KBRepository:
    """Repository for persistent Knowledge Base documents in SQLite."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    def save_document(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        content: str,
        source_path: str,
        metadata_dict: Optional[dict] = None
    ) -> KBDocument:
        created_at = datetime.now().isoformat()
        metadata_str = json.dumps(metadata_dict or {})
        connection = self._database_manager.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO kb_documents 
                (filename, file_type, file_size, content, source_path, created_at, metadata) 
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (filename, file_type, file_size, content, source_path, created_at, metadata_str),
            )
            connection.commit()
            doc_id = cursor.lastrowid
            logger.info("KBRepository: database record added: ID=%s, filename=%s", doc_id, filename)
            return KBDocument(
                id=doc_id,
                filename=filename,
                file_type=file_type,
                file_size=file_size,
                content=content,
                source_path=source_path,
                created_at=created_at,
                metadata=metadata_str
            )
        finally:
            connection.close()

    def get_all_documents(self) -> List[KBDocument]:
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute(
                "SELECT id, filename, file_type, file_size, content, source_path, created_at, metadata FROM kb_documents ORDER BY id DESC"
            ).fetchall()
            logger.info("KBRepository: load complete: count=%d", len(rows))
            return [
                KBDocument(
                    id=row["id"],
                    filename=row["filename"],
                    file_type=row["file_type"],
                    file_size=row["file_size"],
                    content=row["content"],
                    source_path=row["source_path"],
                    created_at=row["created_at"],
                    metadata=row["metadata"]
                )
                for row in rows
            ]
        finally:
            connection.close()

    def get_document_by_id(self, doc_id: int) -> Optional[KBDocument]:
        connection = self._database_manager.get_connection()
        try:
            row = connection.execute(
                "SELECT id, filename, file_type, file_size, content, source_path, created_at, metadata FROM kb_documents WHERE id = ?",
                (doc_id,)
            ).fetchone()
            if row:
                return KBDocument(
                    id=row["id"],
                    filename=row["filename"],
                    file_type=row["file_type"],
                    file_size=row["file_size"],
                    content=row["content"],
                    source_path=row["source_path"],
                    created_at=row["created_at"],
                    metadata=row["metadata"]
                )
            return None
        finally:
            connection.close()

    def delete_document(self, doc_id: int) -> bool:
        connection = self._database_manager.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM kb_documents WHERE id = ?", (doc_id,))
            connection.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info("KBRepository: deleted document record ID=%s", doc_id)
            return success
        finally:
            connection.close()

    def search_documents(self, keywords: List[str], limit: int = 5) -> List[KBDocument]:
        """Simple keyword-based content search matching ALL keywords if possible, falling back to ANY."""
        if not keywords:
            return []
        
        connection = self._database_manager.get_connection()
        try:
            # Let's perform a simple content query
            # We will fetch documents containing any of the keywords and rank/filter them in memory
            # This is robust and doesn't rely on complex SQLite extensions which might not be compiled.
            rows = connection.execute(
                "SELECT id, filename, file_type, file_size, content, source_path, created_at, metadata FROM kb_documents"
            ).fetchall()
            
            scored_docs = []
            for row in rows:
                content_lower = row["content"].lower()
                matches = 0
                for kw in keywords:
                    if kw.lower() in content_lower:
                        matches += 1
                if matches > 0:
                    doc = KBDocument(
                        id=row["id"],
                        filename=row["filename"],
                        file_type=row["file_type"],
                        file_size=row["file_size"],
                        content=row["content"],
                        source_path=row["source_path"],
                        created_at=row["created_at"],
                        metadata=row["metadata"]
                    )
                    scored_docs.append((matches, doc))
            
            # Sort by matches count descending
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            return [doc for score, doc in scored_docs[:limit]]
        finally:
            connection.close()
