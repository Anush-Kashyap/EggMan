from __future__ import annotations

import logging
from typing import Any
from typing import List

from backend.tools.registry import ToolRegistry
from backend.tools.tool import BaseTool


class ToolManager:
    """Coordinates tool registration and execution for future AI tool use."""

    def __init__(self, registry: ToolRegistry | None = None, logger: logging.Logger | None = None) -> None:
        self._registry = registry or ToolRegistry()
        self._logger = logger or logging.getLogger("eggman")

    def register(self, tool_cls: type[BaseTool]) -> None:
        self._registry.register(tool_cls)

    def available_tools(self) -> List[str]:
        return self._registry.names()

    def execute(self, name: str, *args, **kwargs) -> Any:
        self._logger.info("Tool execution started name=%s", name)
        tool = self._registry.create(name)
        try:
            result = tool.execute(*args, **kwargs)
            self._logger.info("Tool execution completed name=%s success=True", name)
            return result
        except Exception as exc:
            self._logger.exception("Tool execution failed name=%s error=%s", name, exc)
            raise
