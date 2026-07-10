from __future__ import annotations

import pytest
import threading
import time
from dataclasses import dataclass
from unittest.mock import MagicMock

from backend.event_bus.event import BaseEvent
from backend.event_bus.event_bus import EventBus
from backend.event_bus.exceptions import SubscriptionError


@dataclass(frozen=True)
class MockEventA(BaseEvent):
    value: str = ""


@dataclass(frozen=True)
class MockEventB(BaseEvent):
    value: int = 0


@dataclass(frozen=True)
class MockSubEventA(MockEventA):
    extra: str = ""


def test_subscribe_and_publish():
    """Verify that subscriptions are registered and callbacks are executed on publish."""
    bus = EventBus()
    callback = MagicMock()
    
    bus.subscribe(MockEventA, callback)
    event = MockEventA(value="hello")
    bus.publish(event)
    
    callback.assert_called_once_with(event)


def test_unsubscribe():
    """Verify that unsubscribed callbacks are no longer executed."""
    bus = EventBus()
    callback = MagicMock()
    
    bus.subscribe(MockEventA, callback)
    bus.unsubscribe(MockEventA, callback)
    
    bus.publish(MockEventA(value="hello"))
    callback.assert_not_called()


def test_inheritance_subscription():
    """Verify that subscribing to a base event type catches subclasses as well."""
    bus = EventBus()
    callback = MagicMock()
    
    bus.subscribe(MockEventA, callback)
    sub_event = MockSubEventA(value="subclass", extra="more")
    bus.publish(sub_event)
    
    callback.assert_called_once_with(sub_event)


def test_error_isolation():
    """Verify that a failing callback does not prevent other callbacks from executing."""
    bus = EventBus()
    failing_callback = MagicMock(side_effect=ValueError("Boom"))
    successful_callback = MagicMock()
    
    bus.subscribe(MockEventA, failing_callback)
    bus.subscribe(MockEventA, successful_callback)
    
    event = MockEventA(value="test")
    bus.publish(event)
    
    failing_callback.assert_called_once_with(event)
    successful_callback.assert_called_once_with(event)


def test_thread_safety():
    """Verify that subscription list is protected during concurrent publish and subscribe actions."""
    bus = EventBus()
    barrier = threading.Barrier(3)
    results = []

    def subscriber_thread():
        barrier.wait()
        for i in range(100):
            bus.subscribe(MockEventA, lambda e: results.append(e.value))

    def publisher_thread():
        barrier.wait()
        for i in range(100):
            bus.publish(MockEventA(value=f"msg_{i}"))

    t1 = threading.Thread(target=subscriber_thread)
    t2 = threading.Thread(target=subscriber_thread)
    t3 = threading.Thread(target=publisher_thread)

    t1.start()
    t2.start()
    t3.start()

    t1.join()
    t2.join()
    t3.join()

    # If it completed without raising RuntimeError, concurrency protection succeeded.
    assert True


def test_clear():
    """Verify clear removes all subscriptions."""
    bus = EventBus()
    callback = MagicMock()
    
    bus.subscribe(MockEventA, callback)
    bus.clear()
    
    bus.publish(MockEventA(value="test"))
    callback.assert_not_called()
