from __future__ import annotations

class EventBusException(Exception):
    """Base exception for all Event Bus errors."""
    pass

class SubscriptionError(EventBusException):
    """Raised when subscription/unsubscription operations fail."""
    pass

class PublishError(EventBusException):
    """Raised when event publication fails."""
    pass
