from __future__ import annotations
from typing import Callable, Any, Type

class Subscription:
    """Represents a subscription to a specific event type."""
    def __init__(self, event_type: Type[Any], callback: Callable[[Any], None]) -> None:
        self.event_type = event_type
        self.callback = callback

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, Subscription):
            return False
        return self.event_type == other.event_type and self.callback == other.callback

    def __hash__(self) -> int:
        return hash((self.event_type, self.callback))
