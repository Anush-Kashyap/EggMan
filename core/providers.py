from __future__ import annotations

import random
from abc import ABC, abstractmethod


class BaseProvider(ABC):
    @abstractmethod
    def generate_reply(self, user_message: str) -> str:
        """Generate a response for the supplied user message."""


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

    def generate_reply(self, user_message: str) -> str:
        return random.choice(self._REPLIES)
