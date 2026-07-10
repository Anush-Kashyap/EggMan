from __future__ import annotations
from dataclasses import dataclass
from backend.event_bus.event import BaseEvent

@dataclass(frozen=True)
class StartupTaskStartedEvent(BaseEvent):
    """Fired when a concurrent/sequential startup task begins execution."""
    task_name: str = ""

@dataclass(frozen=True)
class StartupTaskCompletedEvent(BaseEvent):
    """Fired when a concurrent/sequential startup task completes execution."""
    task_name: str = ""
    duration: float = 0.0
    success: bool = True
    error_message: str | None = None

@dataclass(frozen=True)
class StartupCompletedEvent(BaseEvent):
    """Fired when the entire startup system finishes (successfully or with error)."""
    success: bool = True
    total_time: float = 0.0
    error_message: str | None = None
