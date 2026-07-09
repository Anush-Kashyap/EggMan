from __future__ import annotations

from typing import List, Optional

from backend.knowledge.embedding_provider import EmbeddingProvider


class EmbeddingService:
    """Public embedding interface. Depends only on EmbeddingProvider abstraction."""

    def __init__(self, provider: Optional[EmbeddingProvider] = None) -> None:
        self._provider = provider

    @property
    def provider(self) -> Optional[EmbeddingProvider]:
        return self._provider

    @provider.setter
    def provider(self, provider: EmbeddingProvider) -> None:
        self._provider = provider

    def embed(self, text: str) -> List[float]:
        if self._provider is None:
            raise RuntimeError("No embedding provider configured")
        return self._provider.generate_embedding(text)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        if self._provider is None:
            raise RuntimeError("No embedding provider configured")
        return self._provider.generate_embeddings(texts)

    def is_ready(self) -> bool:
        return self._provider is not None

    def model_name(self) -> str:
        if self._provider is None:
            return "none"
        return self._provider.model_name()
