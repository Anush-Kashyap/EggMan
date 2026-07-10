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
        self._model_pulled = False
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

        payload = {"model": self._model, "input": texts}
        timeout = max(30, len(texts) * 2)  # scale timeout with batch size
        try:
            data = self._post_json("/api/embed", payload, timeout=timeout)
            embeddings = data.get("embeddings", [])
            elapsed_ms = data.get("total_duration", 0) / 1e6
            self._logger.info(
                "OllamaEmbeddingProvider generated %d embeddings in %.1fms model=%s",
                len(embeddings),
                elapsed_ms,
                self._model,
            )
            self._model_pulled = True
            return embeddings
        except RuntimeError as exc:
            error_msg = str(exc).lower()
            if ("not found" in error_msg or "404" in error_msg) and not self._model_pulled:
                self._logger.warning(
                    "Embedding model '%s' not found, attempting to pull it automatically...",
                    self._model,
                )
                self._pull_model()
                # Retry after pull
                data = self._post_json("/api/embed", payload, timeout=timeout)
                embeddings = data.get("embeddings", [])
                elapsed_ms = data.get("total_duration", 0) / 1e6
                self._logger.info(
                    "OllamaEmbeddingProvider generated %d embeddings in %.1fms model=%s (after auto-pull)",
                    len(embeddings),
                    elapsed_ms,
                    self._model,
                )
                self._model_pulled = True
                return embeddings
            self._logger.error(
                "OllamaEmbeddingProvider failed model=%s error=%s",
                self._model,
                exc,
            )
            raise
        except Exception as exc:
            self._logger.error(
                "OllamaEmbeddingProvider failed model=%s error=%s",
                self._model,
                exc,
            )
            raise

    def ensure_model_available(self) -> None:
        """Check if the embedding model is available, pull it if not.

        Call during startup to eagerly download the model so the first
        document upload doesn't have to wait for a pull.
        """
        if self._model_pulled:
            return
        try:
            req = urllib.request.Request(f"{self._base_url}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            available = [m.get("name", "").split(":")[0] for m in data.get("models", [])]
            model_base = self._model.split(":")[0]
            if model_base in available or self._model in [m.get("name", "") for m in data.get("models", [])]:
                self._model_pulled = True
                self._logger.info("Embedding model '%s' is already available", self._model)
                return
            self._logger.info("Embedding model '%s' not found locally, pulling...", self._model)
            self._pull_model()
        except Exception as exc:
            self._logger.warning("Could not verify embedding model availability: %s", exc)

    def _pull_model(self) -> None:
        """Pull the embedding model from Ollama's registry."""
        self._logger.info("Pulling embedding model '%s' from Ollama...", self._model)
        pull_payload = json.dumps({"name": self._model, "stream": False}).encode("utf-8")
        req = urllib.request.Request(
            f"{self._base_url}/api/pull",
            data=pull_payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            # Model pulls can take several minutes for first download
            with urllib.request.urlopen(req, timeout=600) as resp:
                body = resp.read().decode("utf-8", errors="ignore")
                self._logger.info("Embedding model '%s' pulled successfully: %s", self._model, body[:200])
            self._model_pulled = True
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Failed to pull embedding model '{self._model}': {exc.code} {exc.reason} {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"Ollama is not reachable at {self._base_url}. Cannot pull embedding model."
            ) from exc

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

