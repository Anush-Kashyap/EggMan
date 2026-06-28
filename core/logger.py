from __future__ import annotations

import logging
from pathlib import Path

from core.paths import _path


class AppLogger:
    def __init__(self, log_path: str | None = None):
        self._log_path = Path(log_path) if log_path is not None else Path(_path("data", "logs", "eggman.log"))
        self._logger = logging.getLogger("eggman")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False

        if not self._logger.handlers:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            handler = logging.FileHandler(self._log_path, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
            self._logger.addHandler(handler)

    def info(self, message: str) -> None:
        self._logger.info(message)

    def warning(self, message: str) -> None:
        self._logger.warning(message)

    def error(self, message: str) -> None:
        self._logger.error(message)
