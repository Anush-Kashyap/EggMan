from __future__ import annotations

import logging
from typing import Dict, List, Optional

from backend.personas.base_persona import BasePersona
from backend.personas.normal_persona import NormalPersona
from backend.personas.coding_persona import CodingPersona
from backend.personas.party_persona import PartyPersona

logger = logging.getLogger("eggman")

_DEFAULT_PERSONA_KEY = "normal"


class PersonaManager:
    """Singleton registry and switcher for EggMan personas.

    Adding a new persona requires only:
      1. Subclass BasePersona.
      2. Call PersonaManager.get_instance().register(MyPersona()).

    ConversationEngine always calls get_active_persona_prompt() to obtain
    the current persona's prompt module — no hardcoding needed elsewhere.
    """

    _instance: Optional[PersonaManager] = None

    def __init__(self) -> None:
        self._personas: Dict[str, BasePersona] = {}
        self._active_key: str = _DEFAULT_PERSONA_KEY

        # Register built-in personas
        self.register(NormalPersona())
        self.register(CodingPersona())
        self.register(PartyPersona())

    @classmethod
    def get_instance(cls) -> PersonaManager:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Registry API
    # ------------------------------------------------------------------

    def register(self, persona: BasePersona) -> None:
        """Register a persona. Replaces any existing persona with the same key."""
        self._personas[persona.key] = persona
        logger.debug("PersonaManager: registered persona key=%s name=%s", persona.key, persona.display_name)

    def available_personas(self) -> List[BasePersona]:
        """Returns all registered personas in registration order."""
        return list(self._personas.values())

    # ------------------------------------------------------------------
    # Active persona API
    # ------------------------------------------------------------------

    def set_active(self, key: str, old_persona_key: Optional[str] = None) -> bool:
        """Switch the active persona by key. Returns True if the switch succeeded."""
        if key not in self._personas:
            logger.warning("PersonaManager: unknown persona key=%s — ignoring switch", key)
            return False

        prev_key = self._active_key
        self._active_key = key
        new_persona = self._personas[key]

        logger.info(
            "PersonaManager: Persona Changed — old=%s new=%s display=%s",
            prev_key,
            key,
            new_persona.display_name,
        )
        return True

    def get_active(self) -> BasePersona:
        """Returns the currently active BasePersona instance."""
        return self._personas.get(self._active_key, self._personas[_DEFAULT_PERSONA_KEY])

    def get_active_persona_prompt(self) -> str:
        """Returns the persona prompt string to inject into the system prompt."""
        persona = self.get_active()
        prompt = persona.get_persona_prompt()
        logger.debug(
            "PersonaManager: Prompt Module Loaded — persona=%s conversation_persona=%s",
            persona.key,
            persona.display_name,
        )
        return prompt

    def log_developer_info(self) -> None:
        """Emit detailed developer-mode logging for the active persona."""
        persona = self.get_active()
        logger.info("[DEV] Conversation Persona: %s (%s)", persona.display_name, persona.key)
        logger.info("[DEV] Persona Prompt Module Loaded: %s", persona.key)
