from __future__ import annotations
from dataclasses import dataclass
from typing import Any
from backend.event_bus.event import BaseEvent
from backend.registry.common.base_registry import BaseRegistry
from backend.registry.capability.capability import Capability

@dataclass(frozen=True)
class CapabilityRegisteredEvent(BaseEvent):
    capability_id: str = ""

@dataclass(frozen=True)
class CapabilityUnregisteredEvent(BaseEvent):
    capability_id: str = ""

@dataclass(frozen=True)
class CapabilityEnabledEvent(BaseEvent):
    capability_id: str = ""

@dataclass(frozen=True)
class CapabilityDisabledEvent(BaseEvent):
    capability_id: str = ""

class CapabilityRegistry(BaseRegistry[Capability]):
    """Thread-safe registry for managing EggMan capabilities."""

    def __init__(self, event_bus: Any = None) -> None:
        super().__init__()
        self._event_bus = event_bus

    def on_registered(self, item: Capability) -> None:
        if self._event_bus:
            self._event_bus.publish(CapabilityRegisteredEvent(capability_id=item.id))

    def on_unregistered(self, item: Capability) -> None:
        if self._event_bus:
            self._event_bus.publish(CapabilityUnregisteredEvent(capability_id=item.id))

    def set_enabled(self, capability_id: str, enabled: bool) -> None:
        capability = self.get(capability_id)
        if capability.enabled != enabled:
            capability.enabled = enabled
            if self._event_bus:
                if enabled:
                    self._event_bus.publish(CapabilityEnabledEvent(capability_id=capability_id))
                else:
                    self._event_bus.publish(CapabilityDisabledEvent(capability_id=capability_id))
