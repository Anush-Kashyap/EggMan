from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Iterable, Optional

from backend.ai.models import AIRequest, AIResponse
from backend.ai.streaming import StreamingResponse
from core.providers import BaseProvider


class OllamaProvider(BaseProvider):
    """Local Ollama provider using the Ollama HTTP API."""

    DEFAULT_BASE_URL = "http://127.0.0.1:11434"
    DEFAULT_MODEL = "qwen3:8b"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> None:
        super().__init__(provider_name=provider_name)
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self._configured_model = model_name or os.getenv("OLLAMA_MODEL") or self.DEFAULT_MODEL
        self._model_name = self._resolve_model_name()
        self._logger = logging.getLogger("eggman")
        self._logger.info(
            "OllamaProvider initialized base_url=%s model=%s configured_model=%s",
            self._base_url,
            self._model_name,
            self._configured_model,
        )

    @property
    def model_name(self) -> str:
        return self._model_name

    def test_connection(self) -> dict[str, Any]:
        start = time.perf_counter()
        models = self._list_models()
        return {
            "ok": True,
            "base_url": self._base_url,
            "model": self._model_name,
            "available_models": models,
            "elapsed_ms": round((time.perf_counter() - start) * 1000, 1),
        }

    def generate(self, request: AIRequest) -> AIResponse:
        start = time.perf_counter()
        self._logger.info("Ollama generate request model=%s message_len=%d", self._model_name, len(request.user_message or ""))
        payload = {
            "model": request.model_name or self._model_name,
            "prompt": self._format_request_text(request),
            "stream": False,
        }

        try:
            data = self._post_json("/api/generate", payload, timeout=120)
            if "error" in data:
                raise RuntimeError(str(data["error"]))
            text = str(data.get("response", "")).strip()
            self._logger.info(
                "Ollama generate completed model=%s elapsed_ms=%.1f text_len=%d",
                payload["model"],
                (time.perf_counter() - start) * 1000,
                len(text),
            )
            return AIResponse(
                response_text=text,
                model_name=str(payload["model"]),
                finish_reason="completed" if data.get("done", True) else None,
                provider_name=self.provider_name,
                metadata={"ollama": {key: data.get(key) for key in ("total_duration", "load_duration", "eval_count")}},
            )
        except Exception as exc:
            self._logger.exception("Ollama generate failed: %s", exc)
            return AIResponse(error=self._friendly_error(exc), model_name=str(payload["model"]), provider_name=self.provider_name)

    def stream(self, request: AIRequest) -> StreamingResponse:
        payload = {
            "model": request.model_name or self._model_name,
            "prompt": self._format_request_text(request),
            "stream": True,
        }
        self._logger.info("Ollama stream request model=%s message_len=%d", payload["model"], len(request.user_message or ""))
        return StreamingResponse(chunks=self._stream_chunks(payload))

    def _stream_chunks(self, payload: dict[str, Any]) -> Iterable[str]:
        try:
            for data in self._post_stream("/api/generate", payload, timeout=120):
                if "error" in data:
                    raise RuntimeError(str(data["error"]))
                text = data.get("response", "")
                if text:
                    yield str(text)
                if data.get("done"):
                    self._logger.info("Ollama stream completed model=%s", payload["model"])
                    break
        except Exception as exc:
            self._logger.exception("Ollama stream failed: %s", exc)
            yield self._friendly_error(exc)

    def _resolve_model_name(self) -> str:
        if self._configured_model != self.DEFAULT_MODEL:
            try:
                models = self._list_models()
            except RuntimeError:
                return self._configured_model
            if self.DEFAULT_MODEL in models:
                return self.DEFAULT_MODEL
            return self._configured_model
        return self.DEFAULT_MODEL

    def _list_models(self) -> list[str]:
        try:
            data = self._get_json("/api/tags", timeout=5)
        except RuntimeError:
            raise
        models = data.get("models", [])
        names = []
        for model in models:
            if isinstance(model, dict) and model.get("name"):
                names.append(str(model["name"]))
        return names

    def _format_request_text(self, request: AIRequest) -> str:
        parts: list[str] = []
        if request.system_prompt:
            parts.append(request.system_prompt)

        for entry in request.conversation_history:
            sender = getattr(entry, "sender", "user")
            text = getattr(entry, "text", "")
            parts.append(f"{sender}: {text}")

        if request.user_message:
            parts.append(f"User: {request.user_message}")

        return "\n".join(parts)

    def _get_json(self, path: str, timeout: int) -> dict[str, Any]:
        request = urllib.request.Request(f"{self._base_url}{path}", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.URLError as exc:
            raise RuntimeError("Ollama is not running. Start Ollama and try again.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned an invalid response.") from exc

    def _post_json(self, path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        request = self._make_post_request(path, payload)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Ollama request failed: {exc.code} {exc.reason} {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Ollama is not running. Start Ollama and try again.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned an invalid response.") from exc

    def _post_stream(self, path: str, payload: dict[str, Any], timeout: int) -> Iterable[dict[str, Any]]:
        request = self._make_post_request(path, payload)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                for raw_line in response:
                    line = raw_line.decode("utf-8").strip()
                    if not line:
                        continue
                    yield json.loads(line)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Ollama request failed: {exc.code} {exc.reason} {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError("Ollama is not running. Start Ollama and try again.") from exc
        except json.JSONDecodeError as exc:
            raise RuntimeError("Ollama returned an invalid streaming response.") from exc

    def _make_post_request(self, path: str, payload: dict[str, Any]) -> urllib.request.Request:
        return urllib.request.Request(
            f"{self._base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

    def _friendly_error(self, exc: Exception) -> str:
        message = str(exc)
        if "not found" in message.lower():
            return f"Ollama model '{self._model_name}' is not available. Run: ollama pull {self._model_name}"
        return message
