from __future__ import annotations

import random
from abc import ABC, abstractmethod
from typing import Optional

from backend.ai.models import AIRequest, AIResponse
from backend.ai.streaming import StreamingResponse


class BaseProvider(ABC):
    def __init__(self, provider_name: Optional[str] = None) -> None:
        self._provider_name = provider_name or self.__class__.__name__.lower()

    @property
    def provider_name(self) -> str:
        return self._provider_name

    @abstractmethod
    def generate(self, request: AIRequest) -> AIResponse:
        """Generate a structured response for the supplied AI request."""

    @abstractmethod
    def stream(self, request: AIRequest) -> StreamingResponse:
        """Stream a structured response for the supplied AI request."""


class LocalProvider(BaseProvider):
    _REPLIES = [
        "Hi!",
        "Nice to see you.",
        "I'm just an egg.",
        "Eggcellent question.",
        "Interesting!",
        "Tell me more.",
        "I'm thinking... or maybe not.",
        "Yolk's on you.",
        "That's shell-shocking.",
    ]

    def generate(self, request: AIRequest) -> AIResponse:
        reply = random.choice(self._REPLIES)
        return AIResponse(
            response_text=reply,
            model_name="local",
            finish_reason="completed",
            provider_name=self.provider_name,
            token_usage=None,
        )

    def stream(self, request: AIRequest) -> StreamingResponse:
        response = self.generate(request)
        chunks = [chunk for chunk in response.response_text.split(" ") if chunk]
        return StreamingResponse(chunks=chunks or [response.response_text])
