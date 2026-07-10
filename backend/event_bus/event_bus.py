from __future__ import annotations
import logging
import threading
from typing import Dict, Set, Callable, Type, Any, List

from backend.event_bus.event import BaseEvent
from backend.event_bus.exceptions import SubscriptionError

logger = logging.getLogger("eggman")

class EventBus:
    """Thread-safe, decoupled Event Bus for EggMan communication backbone."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._subscribers: Dict[Type[Any], Set[Callable[[Any], None]]] = {}

    def subscribe(self, event_type: Type[Any], callback: Callable[[Any], None]) -> None:
        """Register a subscriber callback for a specific event class."""
        if not isinstance(event_type, type):
            raise SubscriptionError("event_type must be a class/type")
        if not callable(callback):
            raise SubscriptionError("callback must be a callable function")

        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = set()
            self._subscribers[event_type].add(callback)
            logger.debug(
                "EventBus: Subscribed callback=%s to event_type=%s",
                getattr(callback, "__name__", str(callback)),
                event_type.__name__
            )

    def unsubscribe(self, event_type: Type[Any], callback: Callable[[Any], None]) -> None:
        """Unsubscribe a callback from a specific event class."""
        with self._lock:
            if event_type in self._subscribers and callback in self._subscribers[event_type]:
                self._subscribers[event_type].remove(callback)
                if not self._subscribers[event_type]:
                    del self._subscribers[event_type]
                logger.debug(
                    "EventBus: Unsubscribed callback=%s from event_type=%s",
                    getattr(callback, "__name__", str(callback)),
                    event_type.__name__
                )

    def publish(self, event: BaseEvent) -> None:
        """Publish an event to all subscribed callbacks. Prevents listener exceptions from blocking other listeners."""
        if not isinstance(event, BaseEvent):
            logger.warning("EventBus: Refusing to publish non-BaseEvent of type %s", type(event))
            return

        callbacks_to_call: List[Callable[[Any], None]] = []
        event_type = type(event)

        with self._lock:
            # 1. Exact type match
            if event_type in self._subscribers:
                callbacks_to_call.extend(self._subscribers[event_type])
            
            # 2. Base class matches (future proof subclassing support)
            for sub_type, sub_set in self._subscribers.items():
                if sub_type != event_type and issubclass(event_type, sub_type):
                    callbacks_to_call.extend(sub_set)

        # Execute callbacks outside the lock context to prevent deadlock conditions
        for callback in callbacks_to_call:
            try:
                callback(event)
            except Exception as exc:
                logger.error(
                    "EventBus: Callback execution error in callback=%s for event=%s: %s",
                    getattr(callback, "__name__", str(callback)),
                    event_type.__name__,
                    exc,
                    exc_info=True
                )

    def clear(self) -> None:
        """Removes all registered subscriptions."""
        with self._lock:
            self._subscribers.clear()
            logger.debug("EventBus: Cleared all subscriptions")
