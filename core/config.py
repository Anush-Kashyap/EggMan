from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.paths import _path, external_path, resource_path


class ConfigManager:
    _DEFAULTS = {
        "provider": "local",
        "typing_delay": 1000,
        "theme": "light",
        "always_on_top": True,
        "future_ai_model": "",
        "gemini_api_key": "",
    }

    def __init__(self, config_path: str | os.PathLike | None = None):
        self._explicit_path = config_path is not None
        self._path = Path(config_path) if config_path is not None else Path(_path("data", "config.json"))
        self._data: dict[str, Any] = dict(self._DEFAULTS)
        self.load()

    def load(self) -> dict[str, Any]:
        for candidate in self._candidate_paths():
            if not candidate.exists():
                continue
            try:
                with candidate.open("r", encoding="utf-8") as handle:
                    saved = json.load(handle)
                if isinstance(saved, dict):
                    for key, default in self._DEFAULTS.items():
                        if key in saved:
                            self._data[key] = saved[key]
            except (json.JSONDecodeError, OSError):
                pass
        return dict(self._data)

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with self._path.open("w", encoding="utf-8") as handle:
                json.dump(self._data, handle, indent=2)
        except OSError:
            pass

    def get(self, key: str, default: Any | None = None) -> Any:
        return self._data.get(key, default if default is not None else self._DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def _candidate_paths(self) -> list[Path]:
        if self._explicit_path:
            return [self._path]

        candidates = [Path(resource_path("data", "config.json")), Path(external_path("data", "config.json")), self._path]
        unique: list[Path] = []
        for candidate in candidates:
            if candidate not in unique:
                unique.append(candidate)
        return unique
