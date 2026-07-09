from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from backend.knowledge.chunker import TextChunk

logger = logging.getLogger("eggman")


@dataclass(slots=True)
class SearchResult:
    chunk: TextChunk
    score: float
    document_name: str = ""


class VectorStore(ABC):
    """Abstract vector storage. Implement for SQLite, FAISS, Chroma, LanceDB, Qdrant, etc."""

    @abstractmethod
    def store_chunks(
        self,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
        model_name: str,
    ) -> None:
        ...

    @abstractmethod
    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[SearchResult]:
        ...

    @abstractmethod
    def delete_document(self, doc_id: int) -> None:
        ...

    @abstractmethod
    def get_chunk_count(self) -> int:
        ...

    @abstractmethod
    def get_vector_count(self) -> int:
        ...

    @abstractmethod
    def get_all_chunks_for_document(self, doc_id: int) -> List[TextChunk]:
        ...

    @abstractmethod
    def get_database_size(self) -> int:
        ...

    @abstractmethod
    def get_average_chunk_size(self) -> float:
        ...


class SQLiteVectorStore(VectorStore):
    """SQLite-backed vector store using knowledge.db.

    Stores chunks with embeddings as numpy BLOBs.
    Performs cosine similarity search in-memory (suitable for moderate collections).
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._lock = threading.Lock()
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _initialize_schema(self) -> None:
        conn = self._get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    page_number INTEGER,
                    text TEXT NOT NULL,
                    embedding BLOB,
                    model_name TEXT,
                    dimensions INTEGER,
                    metadata TEXT DEFAULT '{}',
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    UNIQUE(doc_id, chunk_index)
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
            conn.execute("""
                CREATE TABLE IF NOT EXISTS store_metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
            """)
            conn.commit()
        finally:
            conn.close()

    def store_chunks(
        self,
        chunks: List[TextChunk],
        embeddings: List[List[float]],
        model_name: str,
    ) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("chunks and embeddings must have the same length")

        conn = self._get_connection()
        try:
            with self._lock:
                for chunk, emb in zip(chunks, embeddings):
                    vector_bytes = np.array(emb, dtype=np.float32).tobytes()
                    conn.execute(
                        """INSERT OR REPLACE INTO chunks
                        (doc_id, chunk_index, page_number, text, embedding, model_name, dimensions)
                        VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (
                            chunk.document_id,
                            chunk.chunk_index,
                            chunk.page_number,
                            chunk.text,
                            vector_bytes,
                            model_name,
                            len(emb),
                        ),
                    )
                conn.commit()
            logger.info(
                "SQLiteVectorStore stored %d chunks for doc_id=%s model=%s",
                len(chunks),
                chunks[0].document_id if chunks else "?",
                model_name,
            )
        finally:
            conn.close()

    def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
    ) -> List[SearchResult]:
        query_vec = np.array(query_embedding, dtype=np.float32)
        query_norm = np.linalg.norm(query_vec)
        if query_norm == 0:
            return []

        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT id, doc_id, chunk_index, page_number, text, embedding, dimensions FROM chunks WHERE embedding IS NOT NULL"
            ).fetchall()
        finally:
            conn.close()

        scored: List[tuple[float, Any]] = []
        for row in rows:
            vec_data = row["embedding"]
            if vec_data is None:
                continue
            stored_vec = np.frombuffer(vec_data, dtype=np.float32)
            stored_norm = np.linalg.norm(stored_vec)
            if stored_norm == 0:
                continue
            similarity = float(np.dot(query_vec, stored_vec) / (query_norm * stored_norm))
            scored.append((similarity, row))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        results: List[SearchResult] = []
        for score, row in top:
            chunk = TextChunk(
                chunk_id=row["id"],
                document_id=row["doc_id"],
                chunk_index=row["chunk_index"],
                page_number=row["page_number"],
                text=row["text"],
            )
            results.append(SearchResult(chunk=chunk, score=score))
        return results

    def delete_document(self, doc_id: int) -> None:
        conn = self._get_connection()
        try:
            with self._lock:
                conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc_id,))
                conn.commit()
            logger.info("SQLiteVectorStore deleted chunks for doc_id=%s", doc_id)
        finally:
            conn.close()

    def get_chunk_count(self) -> int:
        conn = self._get_connection()
        try:
            row = conn.execute("SELECT COUNT(*) AS cnt FROM chunks").fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def get_vector_count(self) -> int:
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM chunks WHERE embedding IS NOT NULL"
            ).fetchone()
            return row["cnt"] if row else 0
        finally:
            conn.close()

    def get_all_chunks_for_document(self, doc_id: int) -> List[TextChunk]:
        conn = self._get_connection()
        try:
            rows = conn.execute(
                "SELECT id, doc_id, chunk_index, page_number, text FROM chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            ).fetchall()
            return [
                TextChunk(
                    chunk_id=row["id"],
                    document_id=row["doc_id"],
                    chunk_index=row["chunk_index"],
                    page_number=row["page_number"],
                    text=row["text"],
                )
                for row in rows
            ]
        finally:
            conn.close()

    def get_database_size(self) -> int:
        try:
            return os.path.getsize(self._db_path)
        except OSError:
            return 0

    def get_average_chunk_size(self) -> float:
        conn = self._get_connection()
        try:
            row = conn.execute(
                "SELECT AVG(LENGTH(text)) AS avg_size FROM chunks"
            ).fetchone()
            return float(row["avg_size"]) if row and row["avg_size"] else 0.0
        finally:
            conn.close()
