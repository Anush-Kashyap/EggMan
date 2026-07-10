from __future__ import annotations
from abc import ABC, abstractmethod
from backend.prompt.prompt_context import PromptContext

class PromptModule(ABC):
    """Abstract base class representing a single modular prompt block."""

    @abstractmethod
    def name(self) -> str:
        """Unique identifier of the module (e.g., 'identity', 'persona')."""
        pass

    @abstractmethod
    def is_static(self) -> bool:
        """True if the module's output is static for a given configuration/state."""
        pass

    @abstractmethod
    def is_applicable(self, context: PromptContext) -> bool:
        """Determines if the module is needed for the current request context."""
        pass

    @abstractmethod
    def generate(self, context: PromptContext) -> str:
        """Generates the prompt string block."""
        pass
