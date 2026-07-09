from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, List, Optional

logger = logging.getLogger("eggman")


class EmbeddingProvider(ABC):
    """Abstract embedding provider. Implement for Ollama, OpenAI, Gemini, etc."""

    @abstractmethod
    def generate_embedding(self, text: str) -> List[float]:
        ...

    @abstractmethod
    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        ...

    @abstractmethod
    def model_name(self) -> str:
        ...


class OllamaEmbeddingProvider(EmbeddingProvider):
    """Generates embeddings via Ollama's /api/embed endpoint."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text",
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._logger = logging.getLogger("eggman")
        self._logger.info(
            "OllamaEmbeddingProvider initialized base_url=%s model=%s",
            self._base_url,
            self._model,
        )

    def model_name(self) -> str:
        return self._model

    def generate_embedding(self, text: str) -> List[float]:
        start = time.perf_counter()
        embeddings = self.generate_embeddings([text])
        elapsed = (time.perf_counter() - start) * 1000
        self._logger.debug(
            "OllamaEmbeddingProvider single embedding generated in %.1fms dims=%d",
            elapsed,
            len(embeddings[0]) if embeddings else 0,
        )
        return embeddings[0] if embeddings else []

    def generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        if not texts:
            return []

        self._check_connection()

        payload = {"model": self._model, "input": texts}
        try:
            data = self._post_json("/api/embed", payload, timeout=30)
            embeddings = data.get("embeddings", [])
            elapsed_ms = data.get("total_duration", 0) / 1e6
            self._logger.info(
                "OllamaEmbeddingProvider generated %d embeddings in %.1fms model=%s",
                len(embeddings),
                elapsed_ms,
                self._model,
            )
            return embeddings
        except Exception as exc:
            self._logger.error(
                "OllamaEmbeddingProvider failed model=%s error=%s",
                self._model,
                exc,
            )
            raise

    def _check_connection(self) -> None:
        """Quick check if Ollama is reachable. Raises RuntimeError if not."""
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3):
                pass
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self._base_url}. "
                "Embeddings cannot be generated. Start Ollama or configure a different provider."
            ) from exc

    def _post_json(self, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Ollama embedding request failed: {exc.code} {exc.reason} {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Ollama is not running. Start Ollama and try again.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned an invalid embedding response.") from exc
