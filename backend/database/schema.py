from __future__ import annotations

import sqlite3


def initialize_schema(connection: sqlite3.Connection) -> None:
    """Create the initial tables needed for future repository-backed features."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS memories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            importance TEXT NOT NULL,
            confidence REAL NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            last_accessed TEXT NOT NULL,
            access_count INTEGER NOT NULL,
            metadata TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS scheduled_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            scheduled_time TEXT NOT NULL,
            repeat_status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS kb_documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            content TEXT NOT NULL,
            source_path TEXT NOT NULL,
            created_at TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'indexed',
            chunk_count INTEGER NOT NULL DEFAULT 0,
            metadata TEXT NOT NULL DEFAULT '{}'
        )
        """
    )

    # Migration: add status column if missing
    try:
        connection.execute("ALTER TABLE kb_documents ADD COLUMN status TEXT NOT NULL DEFAULT 'indexed'")
    except Exception:
        pass
    try:
        connection.execute("ALTER TABLE kb_documents ADD COLUMN chunk_count INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    # Migration: add new memory columns if missing
    for col, definition in [
        ("source", "TEXT NOT NULL DEFAULT 'explicit'"),
        ("expires_at", "TEXT"),
        ("supersedes", "INTEGER"),
        ("embedding_id", "TEXT"),
        ("active", "INTEGER NOT NULL DEFAULT 1"),
    ]:
        try:
            connection.execute(f"ALTER TABLE memories ADD COLUMN {col} {definition}")
        except Exception:
            pass

    # Migrate importance text values to integers (20, 50, 80)
    try:
        connection.execute("UPDATE memories SET importance = '20' WHERE importance = 'low'")
        connection.execute("UPDATE memories SET importance = '50' WHERE importance = 'medium'")
        connection.execute("UPDATE memories SET importance = '80' WHERE importance = 'high'")
    except Exception:
        pass

    connection.commit()
