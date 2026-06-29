from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from core.paths import _path, external_path, resource_path


class ConfigManager:
    _DEFAULTS = {
        "provider": "ollama",
        "typing_delay": 1000,
        "theme": "light",
        "always_on_top": True,
        "ollama_base_url": "http://localhost:11434",
        "ollama_model": "qwen3:8b",
        "voice_whisper_model": "base",
        "wake_word_enabled": True,
        "wake_word_name": "alexa",
        "wake_word_threshold": 0.5,
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
        if self._data.get("provider") in {"gemini", "local"}:
            self._data["provider"] = "ollama"
            self._migrate_legacy_keys()
            self.save()
        return dict(self._data)

    def _migrate_legacy_keys(self) -> None:
        """Drop legacy provider keys and ensure Ollama defaults exist."""
        for legacy_key in ("gemini_api_key", "future_ai_model"):
            self._data.pop(legacy_key, None)
        self._data.setdefault("ollama_base_url", self._DEFAULTS["ollama_base_url"])
        self._data.setdefault("ollama_model", self._DEFAULTS["ollama_model"])
        self._data.setdefault("voice_whisper_model", self._DEFAULTS["voice_whisper_model"])

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
