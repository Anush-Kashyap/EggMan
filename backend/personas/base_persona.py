from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class BasePersona(ABC):
    """Abstract base class for all EggMan personas.

    Each persona only changes the identity, communication style, tone,
    humour and system prompt — all backend capabilities remain identical.

    To add a new persona:
      1. Subclass BasePersona and implement all abstract methods.
      2. Call PersonaManager.register() with an instance of your class.
    """

    @property
    @abstractmethod
    def key(self) -> str:
        """Unique string identifier (e.g. 'normal', 'coding', 'party')."""

    @property
    @abstractmethod
    def display_name(self) -> str:
        """Human-readable name shown in the UI (e.g. 'Normal', 'Coding Guy')."""

    @property
    @abstractmethod
    def emoji(self) -> str:
        """Emoji used to represent this persona in the picker (e.g. '🥚')."""

    @property
    @abstractmethod
    def avatar_path(self) -> Optional[str]:
        """Absolute path to the avatar image, or None to use the default EggMan image."""

    @abstractmethod
    def get_persona_prompt(self) -> str:
        """Returns the persona prompt module that is injected into the system prompt."""
