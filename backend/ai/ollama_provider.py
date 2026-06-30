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

    DEFAULT_BASE_URL = "http://localhost:11434"
    DEFAULT_MODEL = "qwen3:8b"

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> None:
        super().__init__(provider_name=provider_name or "ollama")
        self._base_url = (base_url or os.getenv("OLLAMA_BASE_URL") or self.DEFAULT_BASE_URL).rstrip("/")
        self._configured_model = model_name or os.getenv("OLLAMA_MODEL") or self.DEFAULT_MODEL
        self._logger = logging.getLogger("eggman")
        self._model_name = self._resolve_model_name()
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
        elapsed_ms = lambda: round((time.perf_counter() - start) * 1000, 1)
        try:
            models = self._list_models()
            resolved = self._resolve_model_name_from_list(models)
            self._logger.info(
                "Ollama test_connection ok base_url=%s model=%s elapsed_ms=%.1f",
                self._base_url,
                resolved,
                elapsed_ms(),
            )
            return {
                "ok": True,
                "base_url": self._base_url,
                "model": resolved,
                "configured_model": self._configured_model,
                "available_models": models,
                "elapsed_ms": elapsed_ms(),
            }
        except Exception as exc:
            error = self._friendly_error(exc)
            self._logger.error(
                "Ollama test_connection failed base_url=%s elapsed_ms=%.1f error=%s",
                self._base_url,
                elapsed_ms(),
                error,
            )
            return {
                "ok": False,
                "base_url": self._base_url,
                "model": self._model_name,
                "configured_model": self._configured_model,
                "error": error,
                "elapsed_ms": elapsed_ms(),
            }

    def generate(self, request: AIRequest) -> AIResponse:
        start = time.perf_counter()
        if getattr(request, "images", None):
            model = "qwen2.5vl:7b"
            self._logger.info("Vision model selected")
        else:
            model = request.model_name or self._model_name
        is_vision = (model == "qwen2.5vl:7b")

        self._logger.info("Ollama generate request model=%s message_len=%d", model, len(request.user_message or ""))
        payload = {
            "model": model,
            "prompt": self._format_request_text(request),
            "stream": False,
        }
        if getattr(request, "images", None):
            payload["images"] = request.images

        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        
        if is_vision:
            profiler.start_stage("Vision Processing")
        else:
            profiler.start_stage("Ollama First Token")

        try:
            data = self._post_json("/api/generate", payload, timeout=120)
            if "error" in data:
                raise RuntimeError(str(data["error"]))
            
            if is_vision:
                profiler.stop_stage("Vision Processing")
            else:
                profiler.stop_stage("Ollama First Token")
                # For non-streaming, count generation time as first token time
                profiler.start_stage("Response Generation")
                profiler.stop_stage("Response Generation")

            text = str(data.get("response", "")).strip()
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Populate metrics
            profile = profiler.get_current_profile()
            if profile:
                profile.prompt_tokens = data.get("prompt_eval_count", 0)
                profile.output_tokens = data.get("eval_count", 0)
                profile.load_duration = data.get("load_duration", 0) / 1e9
                profile.prompt_eval_duration = data.get("prompt_eval_duration", 0) / 1e9
                profile.eval_duration = data.get("eval_duration", 0) / 1e9
                profile.prompt_char_count = len(payload.get("prompt", ""))
                profile.provider = self.provider_name
                profile.keep_alive = "5m (default)"
                
                classification = request.metadata.get("classification", "General")
                profile.request_classification = classification
                profile.complexity_score = min(10, max(1, len(request.user_message or "") // 100 + 1))
                
                # Breakdown tokens approximation
                system_len = len(request.system_prompt or "")
                history_len = sum(len(getattr(e, "text", "")) for e in request.conversation_history)
                user_len = len(request.user_message or "")
                total_len = system_len + history_len + user_len
                if total_len > 0:
                    profile.system_prompt_tokens = int((system_len / total_len) * profile.prompt_tokens)
                    profile.user_prompt_tokens = int((user_len / total_len) * profile.prompt_tokens)
                    profile.history_tokens = max(0, profile.prompt_tokens - profile.system_prompt_tokens - profile.user_prompt_tokens)

            if model == "qwen2.5vl:7b":
                self._logger.info("Vision response received")
                self._logger.info("Request duration: %.1fms", elapsed_ms)
            else:
                self._logger.info(
                    "Ollama generate completed model=%s elapsed_ms=%.1f text_len=%d",
                    model,
                    elapsed_ms,
                    len(text),
                )
            return AIResponse(
                response_text=text,
                model_name=str(model),
                finish_reason="completed" if data.get("done", True) else None,
                provider_name=self.provider_name,
                metadata={"ollama": {key: data.get(key) for key in ("total_duration", "load_duration", "eval_count")}},
            )
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._logger.error("Ollama generate failed model=%s elapsed_ms=%.1f error=%s", model, elapsed_ms, exc)
            return AIResponse(error=self._friendly_error(exc, model), model_name=str(model), provider_name=self.provider_name)

    def stream(self, request: AIRequest) -> StreamingResponse:
        start = time.perf_counter()
        if getattr(request, "images", None):
            model = "qwen2.5vl:7b"
            self._logger.info("Vision model selected")
        else:
            model = request.model_name or self._model_name

        payload = {
            "model": model,
            "prompt": self._format_request_text(request),
            "stream": True,
        }
        if getattr(request, "images", None):
            payload["images"] = request.images

        if model == "qwen2.5vl:7b":
            self._logger.info("Vision request sent")

        self._logger.info("Ollama stream request model=%s message_len=%d", model, len(request.user_message or ""))
        return StreamingResponse(chunks=self._stream_chunks(payload, start, request))

    def _stream_chunks(self, payload: dict[str, Any], start: float, request: AIRequest) -> Iterable[str]:
        model = payload["model"]
        is_vision = (model == "qwen2.5vl:7b")
        
        from backend.profiler.performance_profiler import PerformanceProfiler
        profiler = PerformanceProfiler.get_instance()
        first_token = True
        
        if is_vision:
            profiler.start_stage("Vision Processing")
        else:
            profiler.start_stage("Ollama First Token")
            
        try:
            for data in self._post_stream("/api/generate", payload, timeout=120):
                if "error" in data:
                    raise RuntimeError(str(data["error"]))
                
                # Stop first token stage when first text arrives
                if first_token:
                    first_token = False
                    if is_vision:
                        profiler.stop_stage("Vision Processing")
                        profiler.start_stage("Streaming")
                    else:
                        profiler.stop_stage("Ollama First Token")
                        profiler.start_stage("Response Generation")
                
                text = data.get("response", "")
                if text:
                    yield str(text)
                if data.get("done"):
                    elapsed_ms = (time.perf_counter() - start) * 1000

                    # Populate metrics
                    profile = profiler.get_current_profile()
                    if profile:
                        profile.prompt_tokens = data.get("prompt_eval_count", 0)
                        profile.output_tokens = data.get("eval_count", 0)
                        profile.load_duration = data.get("load_duration", 0) / 1e9
                        profile.prompt_eval_duration = data.get("prompt_eval_duration", 0) / 1e9
                        profile.eval_duration = data.get("eval_duration", 0) / 1e9
                        profile.prompt_char_count = len(payload.get("prompt", ""))
                        profile.provider = self.provider_name
                        profile.keep_alive = "5m (default)"
                        
                        classification = request.metadata.get("classification", "General")
                        profile.request_classification = classification
                        profile.complexity_score = min(10, max(1, len(request.user_message or "") // 100 + 1))
                        
                        # Breakdown tokens approximation
                        system_len = len(request.system_prompt or "")
                        history_len = sum(len(getattr(e, "text", "")) for e in request.conversation_history)
                        user_len = len(request.user_message or "")
                        total_len = system_len + history_len + user_len
                        if total_len > 0:
                            profile.system_prompt_tokens = int((system_len / total_len) * profile.prompt_tokens)
                            profile.user_prompt_tokens = int((user_len / total_len) * profile.prompt_tokens)
                            profile.history_tokens = max(0, profile.prompt_tokens - profile.system_prompt_tokens - profile.user_prompt_tokens)

                    if is_vision:
                        self._logger.info("Vision response received")
                        self._logger.info("Request duration: %.1fms", elapsed_ms)
                        profiler.stop_stage("Streaming")
                    else:
                        self._logger.info("Ollama stream completed model=%s elapsed_ms=%.1f", model, elapsed_ms)
                        profiler.stop_stage("Response Generation")
                    break
        except Exception as exc:
            if is_vision:
                profiler.stop_stage("Vision Processing")
                profiler.stop_stage("Streaming")
            else:
                profiler.stop_stage("Ollama First Token")
                profiler.stop_stage("Response Generation")
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._logger.error("Ollama stream failed model=%s elapsed_ms=%.1f error=%s", model, elapsed_ms, exc)
            yield self._friendly_error(exc, model)

    def _resolve_model_name(self) -> str:
        try:
            models = self._list_models()
        except RuntimeError as exc:
            self._logger.warning(
                "Ollama unavailable during init; using configured model=%s error=%s",
                self._configured_model,
                exc,
            )
            return self._configured_model
        return self._resolve_model_name_from_list(models)

    def _resolve_model_name_from_list(self, models: list[str]) -> str:
        if self.DEFAULT_MODEL in models:
            self._logger.info("Ollama model selected=%s (default)", self.DEFAULT_MODEL)
            return self.DEFAULT_MODEL
        if self._configured_model in models:
            self._logger.info(
                "Ollama model selected=%s (configured fallback; %s unavailable)",
                self._configured_model,
                self.DEFAULT_MODEL,
            )
            return self._configured_model
        self._logger.warning(
            "Ollama model fallback to configured=%s (not found in available models)",
            self._configured_model,
        )
        return self._configured_model

    def _list_models(self) -> list[str]:
        data = self._get_json("/api/tags", timeout=5)
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

    def _friendly_error(self, exc: Exception, model_name: Optional[str] = None) -> str:
        message = str(exc)
        model = model_name or self._model_name
        if "not found" in message.lower():
            return f"Ollama model '{model}' is not available. Run: ollama pull {model}"
        return message
