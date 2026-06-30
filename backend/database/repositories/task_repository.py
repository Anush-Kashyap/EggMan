from __future__ import annotations

import logging
from typing import List, Optional
from datetime import datetime
from backend.database.database import DatabaseManager

logger = logging.getLogger("eggman")


class ScheduledTask:
    def __init__(self, id: Optional[int], title: str, scheduled_time: str, repeat_status: str, created_at: str) -> None:
        self.id = id
        self.title = title
        self.scheduled_time = scheduled_time
        self.repeat_status = repeat_status
        self.created_at = created_at


class TaskRepository:
    """Repository for persistent scheduled tasks in SQLite."""

    def __init__(self, database_manager: DatabaseManager) -> None:
        self._database_manager = database_manager

    def save_task(self, title: str, scheduled_time: str, repeat_status: str) -> ScheduledTask:
        created_at = datetime.now().isoformat()
        connection = self._database_manager.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute(
                "INSERT INTO scheduled_tasks (title, scheduled_time, repeat_status, created_at) VALUES (?, ?, ?, ?)",
                (title, scheduled_time, repeat_status, created_at),
            )
            connection.commit()
            task_id = cursor.lastrowid
            logger.info("Schedule loaded / database record added: ID=%s", task_id)
            return ScheduledTask(task_id, title, scheduled_time, repeat_status, created_at)
        finally:
            connection.close()

    def get_all_tasks(self) -> List[ScheduledTask]:
        connection = self._database_manager.get_connection()
        try:
            rows = connection.execute(
                "SELECT id, title, scheduled_time, repeat_status, created_at FROM scheduled_tasks ORDER BY id DESC"
            ).fetchall()
            logger.info("Schedule loaded: count=%d", len(rows))
            return [
                ScheduledTask(row["id"], row["title"], row["scheduled_time"], row["repeat_status"], row["created_at"])
                for row in rows
            ]
        finally:
            connection.close()

    def delete_task(self, task_id: int) -> bool:
        connection = self._database_manager.get_connection()
        try:
            cursor = connection.cursor()
            cursor.execute("DELETE FROM scheduled_tasks WHERE id = ?", (task_id,))
            connection.commit()
            success = cursor.rowcount > 0
            if success:
                logger.info("Schedule deleted: ID=%s", task_id)
            return success
        finally:
            connection.close()
