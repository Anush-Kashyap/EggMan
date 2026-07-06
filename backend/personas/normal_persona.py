from __future__ import annotations

from typing import Optional

from backend.personas.base_persona import BasePersona
from core.paths import ASSETS_DIR


class NormalPersona(BasePersona):
    """Default EggMan persona: calm, friendly, helpful and natural."""

    @property
    def key(self) -> str:
        return "normal"

    @property
    def display_name(self) -> str:
        return "Normal"

    @property
    def emoji(self) -> str:
        return "🥚"

    @property
    def avatar_path(self) -> Optional[str]:
        # Normal EggMan uses the standard active/inactive/thinking images — return None
        return None

    def get_persona_prompt(self) -> str:
        return (
            "PERSONA: NORMAL EGGMAN\n"
            "- You are EggMan in your default form: calm, friendly, practical, and helpful.\n"
            "- Maintain a balanced, human-like tone without leaning into any particular theme.\n"
            "- Be genuinely curious and honest, avoiding over-enthusiasm or robotic formality."
        )
