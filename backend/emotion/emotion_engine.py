from __future__ import annotations

from backend.emotion.mood import Mood
from backend.emotion.state import EmotionalState


class EmotionEngine:
    """Lightweight engine that updates a simple emotional state from conversation events."""

    def __init__(self, state: EmotionalState | None = None) -> None:
        self._state = state or EmotionalState()

    @property
    def state(self) -> EmotionalState:
        return self._state

    def observe(self, event: str) -> EmotionalState:
        lowered = event.lower()
        if "hello" in lowered or "hi" in lowered:
            self._state.mood = Mood.HAPPY.value
        elif "error" in lowered or "fail" in lowered:
            self._state.mood = Mood.SAD.value
        elif "?" in lowered:
            self._state.mood = Mood.CURIOUS.value
        else:
            self._state.mood = Mood.NEUTRAL.value
        return self._state
