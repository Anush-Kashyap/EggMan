from __future__ import annotations
from dataclasses import dataclass, field
from typing import List
from backend.registry.common.metadata import RegistryMetadata

@dataclass
class CapabilityMetadata(RegistryMetadata):
    category: str = "general"
    version: str = "1.0.0"
    experimental: bool = False
    dependencies: List[str] = field(default_factory=list)
    health_status: str = "Healthy"  # Healthy, Unavailable, Initializing, Disabled

class Capability:
    """Represents an offline capability/feature description in EggMan."""
    def __init__(self, metadata: CapabilityMetadata) -> None:
        self.metadata = metadata

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def description(self) -> str:
        return self.metadata.description

    @property
    def enabled(self) -> bool:
        return self.metadata.enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self.metadata.enabled = value

    @property
    def health_status(self) -> str:
        return self.metadata.health_status

    @health_status.setter
    def health_status(self, value: str) -> None:
        self.metadata.health_status = value
