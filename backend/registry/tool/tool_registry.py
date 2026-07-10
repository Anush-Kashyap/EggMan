from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from backend.event_bus.event import BaseEvent
from backend.registry.common.base_registry import BaseRegistry
from backend.registry.tool.tool import Tool

@dataclass(frozen=True)
class ToolRegisteredEvent(BaseEvent):
    tool_id: str = ""
    capability_id: str = ""

@dataclass(frozen=True)
class ToolUnregisteredEvent(BaseEvent):
    tool_id: str = ""
    capability_id: str = ""

@dataclass(frozen=True)
class ToolEnabledEvent(BaseEvent):
    tool_id: str = ""

@dataclass(frozen=True)
class ToolDisabledEvent(BaseEvent):
    tool_id: str = ""

class ToolRegistry(BaseRegistry[Tool]):
    """Thread-safe registry for managing EggMan tools."""

    def __init__(self, event_bus: Any = None) -> None:
        super().__init__()
        self._event_bus = event_bus

    def on_registered(self, item: Tool) -> None:
        if self._event_bus:
            self._event_bus.publish(
                ToolRegisteredEvent(tool_id=item.id, capability_id=item.capability_id)
            )

    def on_unregistered(self, item: Tool) -> None:
        if self._event_bus:
            self._event_bus.publish(
                ToolUnregisteredEvent(tool_id=item.id, capability_id=item.capability_id)
            )

    def set_enabled(self, tool_id: str, enabled: bool) -> None:
        tool = self.get(tool_id)
        if tool.enabled != enabled:
            tool.enabled = enabled
            if self._event_bus:
                if enabled:
                    self._event_bus.publish(ToolEnabledEvent(tool_id=tool_id))
                else:
                    self._event_bus.publish(ToolDisabledEvent(tool_id=tool_id))
