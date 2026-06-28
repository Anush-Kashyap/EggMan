from __future__ import annotations

from collections.abc import Callable
from typing import Dict, Type

from backend.tools.tool import BaseTool

ToolFactory = Callable[[], BaseTool]


class ToolRegistry:
    """Simple registry for tools that can be discovered by name."""

    def __init__(self) -> None:
        self._tools: Dict[str, ToolFactory] = {}
        self._public_names: set[str] = set()

    def register(self, tool_cls: Type[BaseTool], name: str | None = None) -> None:
        if not issubclass(tool_cls, BaseTool):
            raise TypeError("Registered tools must inherit BaseTool")
        self.register_factory(name or tool_cls.name or tool_cls.__name__.lower(), tool_cls)
        self._tools.setdefault(tool_cls.__name__.lower(), tool_cls)

    def register_factory(self, name: str, factory: ToolFactory) -> None:
        if not name:
            raise ValueError("Tool name is required")
        key = name.lower()
        self._tools[key] = factory
        self._public_names.add(key)

    def create(self, name: str) -> BaseTool:
        factory = self._tools.get(name.lower())
        if factory is None:
            raise KeyError(f"Unknown tool: {name}")
        tool = factory()
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool factory for {name} did not return a BaseTool")
        return tool

    def names(self) -> list[str]:
        return sorted(self._public_names)
