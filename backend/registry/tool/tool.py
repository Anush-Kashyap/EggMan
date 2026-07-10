from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any, List
from backend.registry.common.metadata import RegistryMetadata

@dataclass
class ToolMetadata(RegistryMetadata):
    capability_id: str = ""
    parameter_schema: Dict[str, Any] = field(default_factory=dict)
    aliases: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)

class Tool:
    """Represents a wrapped executable tool in EggMan."""
    def __init__(self, metadata: ToolMetadata, executable: Any = None) -> None:
        self.metadata = metadata
        self.executable = executable  # References the actual tool class instance

    @property
    def id(self) -> str:
        return self.metadata.id

    @property
    def capability_id(self) -> str:
        return self.metadata.capability_id

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
