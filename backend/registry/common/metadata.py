from __future__ import annotations
from dataclasses import dataclass, field
from typing import List

@dataclass
class RegistryMetadata:
    """Base metadata model for registry items."""
    id: str
    name: str
    description: str
    enabled: bool = True
    tags: List[str] = field(default_factory=list)
