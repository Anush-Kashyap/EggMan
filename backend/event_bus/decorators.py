from __future__ import annotations
from typing import Callable, Any, Type

def on_event(event_type: Type[Any]):
    """Decorator to tag a method as an event handler."""
    def decorator(func: Callable[[Any], None]) -> Callable[[Any], None]:
        setattr(func, "_subscribed_event_type", event_type)
        return func
    return decorator
