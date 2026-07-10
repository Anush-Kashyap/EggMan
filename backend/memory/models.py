from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict


class MemoryCategory(str, Enum):
    """Supported memory categories for Memory System v2."""

    PREFERENCE = "preference"
    PROJECT = "project"
    GOAL = "goal"
    SKILL = "skill"
    HABIT = "habit"
    PERSONAL_FACT = "personal_fact"
    TEMPORARY = "temporary"
    PERMANENT = "permanent"

    # Legacy compatibility categories
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    RELATIONSHIP = "relationship"


class ImportanceLevel(str, Enum):
    """Legacy relative importance levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(slots=True)
class MemoryRecord:
    """Strongly typed memory model used by the Memory System v2."""

    id: int | None = None
    category: MemoryCategory = MemoryCategory.PERMANENT
    key: str = ""
    value: str = ""
    importance: int = 50  # 0 to 100 importance score
    confidence: float = 0.0  # 0.0 to 1.0 confidence score
    source: str = "explicit"  # "explicit", "inferred", etc.
    created_at: str = ""
    updated_at: str = ""
    last_accessed: str = ""
    access_count: int = 0
    expires_at: str | None = None  # ISO timestamp of expiration or None
    supersedes: int | None = None  # ID of a memory record that this supersedes
    embedding_id: str | None = None  # Optional ID for future semantic retrieval
    active: bool = True  # True if active, False if superseded/expired/inactive
    metadata: Dict[str, Any] = field(default_factory=dict)
