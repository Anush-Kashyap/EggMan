from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EmotionalState:
    """Simple emotional state carried through the backend."""

    mood: str = "neutral"
    energy: str = "medium"
    confidence: str = "medium"
