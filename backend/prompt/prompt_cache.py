from __future__ import annotations
import logging
from typing import Dict

logger = logging.getLogger("eggman")

class PromptCache:
    """Caches generated static prompt content to reduce computation."""

    def __init__(self) -> None:
        self._cache: Dict[str, str] = {}
        self.hits = 0
        self.misses = 0

    def get(self, key: str) -> str | None:
        """Get cached content."""
        if key in self._cache:
            self.hits += 1
            return self._cache[key]
        self.misses += 1
        return None

    def set(self, key: str, value: str) -> None:
        """Set cached content."""
        self._cache[key] = value

    def clear(self) -> None:
        """Clear all cached contents."""
        self._cache.clear()
        self.hits = 0
        self.misses = 0
