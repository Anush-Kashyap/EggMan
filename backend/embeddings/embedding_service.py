from __future__ import annotations

import hashlib
import math
from typing import List, Protocol


class EmbeddingProvider(Protocol):
    """Protocol for future embedding providers such as local or remote services."""

    def embed(self, text: str) -> List[float]:
        ...


class LocalEmbeddingProvider:
    """Simple deterministic local embedding provider used until a real model is configured."""

    def embed(self, text: str) -> List[float]:
        tokens = [token.lower() for token in text.replace("\n", " ").split() if token]
        if not tokens:
            return [0.0] * 8

        vector: List[float] = []
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            vector.extend(float(b) / 255.0 for b in digest[:4])
        if len(vector) < 8:
            vector.extend([0.0] * (8 - len(vector)))
        return [round(value, 6) for value in vector[:8]]


class EmbeddingService:
    """Abstraction for generating embeddings without tying callers to a specific provider."""

    def __init__(self, provider: EmbeddingProvider | None = None) -> None:
        self._provider = provider or LocalEmbeddingProvider()

    def embed(self, text: str) -> List[float]:
        return self._provider.embed(text)
