from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class MemoryCategory(str, Enum):
    """Supported memory categories for future long-term memory storage."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    RELATIONSHIP = "relationship"


@dataclass(slots=True)
class MemoryEntry:
    """Representation of a single memory item that can later be stored in SQLite."""

    memory_id: str
    category: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class MemoryQuery:
    """Simple query object for retrieving memories without tying callers to a backend."""

    category: str | None = None
    limit: int = 5
    query_text: str | None = None
