from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from backend.database.database import DatabaseManager
from backend.memory.models import ImportanceLevel, MemoryCategory, MemoryRecord


class MemoryRepository:
    """Persistence layer for long-term memories. No business logic lives here."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    def save_memory(self, memory: MemoryRecord) -> MemoryRecord:
        connection = self._database_manager.get_connection()
        try:
            if memory.created_at == "":
                memory.created_at = datetime.now().isoformat(timespec="seconds")
            if memory.updated_at == "":
                memory.updated_at = memory.created_at
            cursor = connection.execute(
                """
                INSERT INTO memories (
                    category, key, value, importance, confidence, created_at, updated_at,
                    last_accessed, access_count, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory.category.value,
                    memory.key,
                    memory.value,
                    memory.importance.value,
                    memory.confidence,
                    memory.created_at,
                    memory.updated_at,
                    memory.last_accessed,
                    memory.access_count,
                    str(memory.metadata),
                ),
            )
            memory.id = int(cursor.lastrowid)
            connection.commit()
            return memory
        finally:
            connection.close()

    def update_memory(self, memory: MemoryRecord) -> MemoryRecord:
        connection = self._database_manager.get_connection()
        try:
            memory.updated_at = datetime.now().isoformat(timespec="seconds")
            connection.execute(
                """
                UPDATE memories
                SET category = ?, key = ?, value = ?, importance = ?, confidence = ?,
                    updated_at = ?, last_accessed = ?, access_count = ?, metadata = ?
                WHERE id = ?
                """,
                (
                    memory.category.value,
                    memory.key,
                    memory.value,
                    memory.importance.value,
                    memory.confidence,
                    memory.updated_at,
                    memory.last_accessed,
                    memory.access_count,
                    str(memory.metadata),
                    memory.id,
                ),
            )
            connection.commit()
            return memory
        finally:
            connection.close()

    def get_memory(self, memory_id: int) -> Optional[MemoryRecord]:
        connection = self._database_manager.get_connection()
        try:
            row = connection.execute("SELECT * FROM memories WHERE id = ?", (memory_id,)).fetchone()
            return self._row_to_memory(row) if row else None
        finally:
            connection.close()

    def get_all_memories(self) -> List[MemoryRecord]:
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute("SELECT * FROM memories ORDER BY updated_at DESC").fetchall()
            return [self._row_to_memory(row) for row in rows]
        finally:
            connection.close()

    def find_memory(self, key: str, value: str) -> Optional[MemoryRecord]:
        connection = self._database_manager.get_connection()
        try:
            row = connection.execute(
                "SELECT * FROM memories WHERE key = ? AND value = ? ORDER BY updated_at DESC LIMIT 1",
                (key, value),
            ).fetchone()
            return self._row_to_memory(row) if row else None
        finally:
            connection.close()

    def search_memories(self, query: str, limit: int = 10) -> List[MemoryRecord]:
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute(
                "SELECT * FROM memories WHERE key LIKE ? OR value LIKE ? ORDER BY updated_at DESC LIMIT ?",
                (f"%{query}%", f"%{query}%", limit),
            ).fetchall()
            return [self._row_to_memory(row) for row in rows]
        finally:
            connection.close()

    def mark_accessed(self, memories: List[MemoryRecord]) -> None:
        if not memories:
            return

        accessed_at = datetime.now().isoformat(timespec="seconds")
        connection = self._database_manager.get_connection()
        try:
            connection.executemany(
                """
                UPDATE memories
                SET last_accessed = ?, access_count = access_count + 1
                WHERE id = ?
                """,
                [(accessed_at, memory.id) for memory in memories if memory.id is not None],
            )
            connection.commit()
        finally:
            connection.close()

    def delete_memory(self, memory_id: int) -> None:
        connection = self._database_manager.get_connection()
        try:
            connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            connection.commit()
        finally:
            connection.close()

    def _row_to_memory(self, row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            category=MemoryCategory(row["category"]),
            key=row["key"],
            value=row["value"],
            importance=ImportanceLevel(row["importance"]),
            confidence=float(row["confidence"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            last_accessed=row["last_accessed"],
            access_count=int(row["access_count"]),
            metadata={},
        )
