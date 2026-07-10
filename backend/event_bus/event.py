from __future__ import annotations
import uuid
import time
from dataclasses import dataclass, field
from typing import Dict, Any

@dataclass(frozen=True)
class BaseEvent:
    """Base event class. All custom events must inherit from this class."""
    event_id: uuid.UUID = field(default_factory=uuid.uuid4, init=False)
    timestamp: float = field(default_factory=time.time, init=False)
    source: str = "system"
    metadata: Dict[str, Any] = field(default_factory=dict, hash=False)
