from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from core.paths import _path


class DatabaseManager:
    """Small SQLite wrapper that creates the file and schema as needed."""

    def __init__(self, database_path: Optional[Path | str] = None) -> None:
        self._database_path = Path(database_path) if database_path is not None else Path(_path("database", "eggman.sqlite3"))
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self.initialize()

    @property
    def database_path(self) -> Path:
        return self._database_path

    def initialize(self) -> None:
        connection = self.get_connection()
        try:
            self._initialize_schema(connection)
        finally:
            connection.close()

    def _initialize_schema(self, connection: sqlite3.Connection) -> None:
        from backend.database.schema import initialize_schema

        initialize_schema(connection)

    def get_connection(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        return connection

    def close(self) -> None:
        return None
