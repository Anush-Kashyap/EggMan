from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.database.database import DatabaseManager
from backend.knowledge.models import KBDocument

logger = logging.getLogger("eggman")


class KBRepository:
    """Repository for persistent Knowledge Base documents in eggman.db."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    @staticmethod
    def _row_to_document(row: Any) -> KBDocument:
        return KBDocument(
            id=row["id"],
            filename=row["filename"],
            file_type=row["file_type"],
            file_size=row["file_size"],
            content=row["content"],
            source_path=row["source_path"],
            created_at=row["created_at"],
            status=row["status"],
            chunk_count=row["chunk_count"],
            metadata=row["metadata"],
        )

    def save_document(
        self,
        filename: str,
        file_type: str,
        file_size: int,
        content: str,
        source_path: str,
        metadata_dict: Optional[dict] = None,
    ) -> KBDocument:
        created_at = datetime.now().isoformat()
        metadata_str = json.dumps(metadata_dict or {})
        status = metadata_dict.get("status", "indexed") if isinstance(metadata_dict, dict) else "indexed"
        connection = self._database_manager.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                """INSERT INTO kb_documents
                (filename, file_type, file_size, content, source_path, created_at, status, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (filename, file_type, file_size, content, source_path, created_at, status, metadata_str),
            )
            connection.commit()
            doc_id = cursor.lastrowid
            logger.info("KBRepository: record added id=%s filename=%s status=%s", doc_id, filename, status)
            return KBDocument(
                id=doc_id,
                filename=filename,
                file_type=file_type,
                file_size=file_size,
                content=content,
                source_path=source_path,
                created_at=created_at,
                status=status,
                metadata=metadata_str,
            )
        finally:
            connection.close()

    def get_all_documents(self) -> List[KBDocument]:
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute(
                "SELECT id, filename, file_type, file_size, content, source_path, created_at, status, chunk_count, metadata FROM kb_documents ORDER BY id DESC"
            ).fetchall()
            return [self._row_to_document(row) for row in rows]
        finally:
            connection.close()

    def get_document_by_id(self, doc_id: int) -> Optional[KBDocument]:
        connection = self._database_manager.get_connection()
        try:
            row = connection.execute(
                "SELECT id, filename, file_type, file_size, content, source_path, created_at, status, chunk_count, metadata FROM kb_documents WHERE id = ?",
                (doc_id,),
            ).fetchone()
            return self._row_to_document(row) if row else None
        finally:
            connection.close()

    def update_status(self, doc_id: int, status: str) -> None:
        connection = self._database_manager.get_connection()
        try:
            connection.execute("UPDATE kb_documents SET status = ? WHERE id = ?", (status, doc_id))
            connection.commit()
            logger.debug("KBRepository: updated status doc_id=%s status=%s", doc_id, status)
        finally:
            connection.close()

    def update_content(self, doc_id: int, content: str) -> None:
        connection = self._database_manager.get_connection()
        try:
            connection.execute("UPDATE kb_documents SET content = ? WHERE id = ?", (content, doc_id))
            connection.commit()
        finally:
            connection.close()

    def update_chunk_count(self, doc_id: int, count: int) -> None:
        connection = self._database_manager.get_connection()
        try:
            connection.execute("UPDATE kb_documents SET chunk_count = ? WHERE id = ?", (count, doc_id))
            connection.commit()
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
                logger.info("KBRepository: deleted document id=%s", doc_id)
            return success
        finally:
            connection.close()

    def search_documents(self, keywords: List[str], limit: int = 5) -> List[KBDocument]:
        if not keywords:
            return []
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute(
                "SELECT id, filename, file_type, file_size, content, source_path, created_at, status, chunk_count, metadata FROM kb_documents"
            ).fetchall()
            scored_docs = []
            for row in rows:
                content_lower = row["content"].lower()
                matches = sum(1 for kw in keywords if kw.lower() in content_lower)
                if matches > 0:
                    scored_docs.append((matches, self._row_to_document(row)))
            scored_docs.sort(key=lambda x: x[0], reverse=True)
            return [doc for score, doc in scored_docs[:limit]]
        finally:
            connection.close()
