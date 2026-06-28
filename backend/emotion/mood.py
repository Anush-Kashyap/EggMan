from __future__ import annotations

from enum import Enum


class Mood(str, Enum):
    """Lightweight mood vocabulary for future emotional context."""

    HAPPY = "happy"
    CALM = "calm"
    NEUTRAL = "neutral"
    CURIOUS = "curious"
    SAD = "sad"
