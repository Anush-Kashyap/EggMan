from __future__ import annotations

class RegistryError(Exception):
    """Base exception for all registry-related errors."""
    pass

class DuplicateRegistrationError(RegistryError):
    """Raised when an item is registered with an ID that already exists."""
    pass

class ValidationError(RegistryError):
    """Raised when metadata or capability constraints fail validation."""
    pass

class ItemNotFoundError(RegistryError):
    """Raised when an item is requested but not found in the registry."""
    pass
