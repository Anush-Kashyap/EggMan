from __future__ import annotations

from typing import List, Optional, Tuple

from backend.database.database import DatabaseManager


class ConversationRepository:
    """Repository for conversation persistence without leaking SQL into the engine."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    def save_message(self, sender: str, message: str, created_at: Optional[str] = None) -> None:
        connection = self._database_manager.get_connection()
        try:
            connection.execute(
                "INSERT INTO conversations (sender, message, created_at) VALUES (?, ?, ?)",
                (sender, message, created_at or ""),
            )
            connection.commit()
        finally:
            connection.close()

    def load_recent_messages(self, limit: int = 50) -> List[Tuple[str, str, str]]:
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute(
                "SELECT sender, message, created_at FROM conversations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [(row["sender"], row["message"], row["created_at"]) for row in rows]
        finally:
            connection.close()

    def clear_history(self) -> None:
        connection = self._database_manager.get_connection()
        try:
            connection.execute("DELETE FROM conversations")
            connection.commit()
        finally:
            connection.close()
