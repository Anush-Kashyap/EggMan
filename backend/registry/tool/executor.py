from __future__ import annotations
from typing import Any

class ToolExecutor:
    """Execution wrapper to invoke registry-wrapped tools dynamically."""

    def __init__(self, registry: Any) -> None:
        self.registry = registry

    def execute(self, tool_id: str, *args: Any, **kwargs: Any) -> Any:
        """Retrieve and execute a tool by its ID."""
        tool = self.registry.get(tool_id)
        if not tool.enabled:
            raise ValueError(f"Tool '{tool_id}' is disabled.")

        exec_obj = tool.executable
        if callable(exec_obj):
            return exec_obj(*args, **kwargs)
        elif hasattr(exec_obj, "execute"):
            return exec_obj.execute(*args, **kwargs)
        elif hasattr(exec_obj, "run"):
            return exec_obj.run(*args, **kwargs)

        raise TypeError(f"Tool executable for '{tool_id}' is not executable.")
