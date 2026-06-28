from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseTool(ABC):
    """Base interface for provider-agnostic tools that may be invoked later."""

    name: str = ""

    @abstractmethod
    def execute(self, *args, **kwargs) -> Any:
        """Execute the tool and return a structured or string result."""


class PlaceholderTool(BaseTool):
    """Simple placeholder tool used to keep the framework extensible."""

    name = "placeholder"

    def execute(self, *args, **kwargs) -> str:
        return "Tool placeholder"
