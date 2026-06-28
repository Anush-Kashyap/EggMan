from __future__ import annotations

import json
import logging
import os
import time
import urllib.error
import urllib.request
from typing import Any, Optional

from backend.ai.models import AIRequest, AIResponse
from backend.ai.streaming import StreamingResponse
from core.providers import BaseProvider


class GeminiProvider(BaseProvider):
    """Google Gemini provider using an API key and REST transport."""

    DEFAULT_MODEL = "gemini-2.5-flash"
    FALLBACK_MODEL = "gemini-2.5-pro"
    DEFAULT_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: Optional[str] = None,
        provider_name: Optional[str] = None,
    ) -> None:
        super().__init__(provider_name=provider_name)
        self._api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("EGGMAN_GEMINI_API_KEY")
        self._model_name = model_name or self.DEFAULT_MODEL
        self._endpoint = f"{self.DEFAULT_ENDPOINT}/{self._model_name}:generateContent"
        self._logger = logging.getLogger("eggman")

        if not self._api_key:
            raise ValueError(
                "Gemini API key is required. Set GEMINI_API_KEY or EGGMAN_GEMINI_API_KEY in your environment."
            )
        self._logger.info(
            "GeminiProvider initialized endpoint=%s model=%s api_key_present=%s",
            self._endpoint,
            self._model_name,
            bool(self._api_key),
        )

    def generate(self, request: AIRequest) -> AIResponse:
        start = time.perf_counter()
        self._logger.debug(
            "GeminiProvider.generate entering endpoint=%s model=%s api_key_present=%s",
            self._endpoint,
            self._model_name,
            bool(self._api_key),
        )
        prompt_text = self._format_request_text(request)
        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt_text},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512,
            },
        }

        try:
            response_data = self._call_api(payload)
            text = self._parse_response(response_data)
            self._logger.debug(
                "GeminiProvider.generate leaving in %.1fms text_len=%d",
                (time.perf_counter() - start) * 1000,
                len(text),
            )
            return AIResponse(
                response_text=text,
                model_name=self._model_name,
                finish_reason="completed",
                provider_name=self.provider_name,
            )
        except Exception as exc:
            self._logger.exception("GeminiProvider.generate failed: %s", exc)
            return AIResponse(error=str(exc), provider_name=self.provider_name)

    def stream(self, request: AIRequest) -> StreamingResponse:
        response = self.generate(request)
        return StreamingResponse(chunks=[response.response_text or response.error or ""])

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

    def _call_api(self, payload: dict[str, Any]) -> dict[str, Any]:
        start = time.perf_counter()
        data = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            self._endpoint,
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": self._api_key,
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                self._logger.debug("Gemini API HTTP status=%s", response.status)
                raw = response.read()
                self._logger.debug(
                    "GeminiProvider._call_api received %d bytes in %.1fms",
                    len(raw),
                    (time.perf_counter() - start) * 1000,
                )
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode('utf-8', errors='ignore')
            self._logger.error("Gemini API HTTP error status=%s reason=%s body=%s", exc.code, exc.reason, error_body)
            if exc.code == 503 and self._model_name == self.DEFAULT_MODEL:
                self._try_fallback_model()
                return self._call_api(payload)
            raise RuntimeError(f"Gemini API request failed: {exc.code} {exc.reason}\n{error_body}")
        except urllib.error.URLError as exc:
            self._logger.exception("Gemini transport error: %s", exc)
            raise RuntimeError(f"Gemini transport error: {exc.reason}")

    def _try_fallback_model(self) -> None:
        if self._model_name == self.DEFAULT_MODEL and hasattr(self, 'FALLBACK_MODEL'):
            self._model_name = self.FALLBACK_MODEL
            self._endpoint = f"{self.DEFAULT_ENDPOINT}/{self._model_name}:generateContent"

    def _parse_response(self, response_data: dict[str, Any]) -> str:
        if not isinstance(response_data, dict):
            raise ValueError("Unexpected Gemini response format")

        if "candidates" in response_data and response_data["candidates"]:
            candidate = response_data["candidates"][0]
            if isinstance(candidate, dict):
                content = candidate.get("content", {})
                if isinstance(content, dict):
                    parts = content.get("parts", [])
                    return "".join(part.get("text", "") for part in parts if isinstance(part, dict))
                if isinstance(content, str):
                    return content

        if "outputs" in response_data and response_data["outputs"]:
            output = response_data["outputs"][0]
            if isinstance(output, dict):
                return output.get("content", "")

        return json.dumps(response_data)
