from __future__ import annotations
import logging
from typing import Dict, List
from backend.prompt.prompt_module import PromptModule

logger = logging.getLogger("eggman")

class PromptRegistry:
    """Registry where PromptModules are registered and discovered."""

    _modules: Dict[str, PromptModule] = {}

    @classmethod
    def register(cls, module: PromptModule) -> None:
        """Registers a prompt module instance."""
        name = module.name()
        cls._modules[name] = module
        logger.debug("PromptRegistry: Registered module name=%s", name)

    @classmethod
    def get_modules(cls) -> List[PromptModule]:
        """Returns all registered prompt modules."""
        return list(cls._modules.values())

    @classmethod
    def get(cls, name: str) -> PromptModule | None:
        """Retrieves a registered module by name."""
        return cls._modules.get(name)

    @classmethod
    def clear(cls) -> None:
        """Clears the registry."""
        cls._modules.clear()
