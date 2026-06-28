from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class MemoryCategory(str, Enum):
    """Supported long-term memory categories."""

    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PREFERENCE = "preference"
    RELATIONSHIP = "relationship"


class ImportanceLevel(str, Enum):
    """Relative importance of a remembered fact."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class MemoryRecord:
    """Strongly typed memory model used by the repository and manager."""

    id: int | None = None
    category: MemoryCategory = MemoryCategory.SEMANTIC
    key: str = ""
    value: str = ""
    importance: ImportanceLevel = ImportanceLevel.MEDIUM
    confidence: float = 0.0
    created_at: str = ""
    updated_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
