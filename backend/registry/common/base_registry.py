from __future__ import annotations
import threading
from typing import Dict, Any, List, Iterator, TypeVar, Generic
from backend.registry.common.exceptions import DuplicateRegistrationError, ItemNotFoundError, ValidationError

T = TypeVar('T')

class BaseRegistry(Generic[T]):
    """Generic, thread-safe base registry class providing core registration operations."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._items: Dict[str, T] = {}

    def register(self, item: T) -> None:
        """Register an item in the registry. Performs validation and duplicate check."""
        item_id = self._get_item_id(item)
        self.validate(item)
        
        with self._lock:
            if item_id in self._items:
                raise DuplicateRegistrationError(f"Item with ID '{item_id}' already registered.")
            self._items[item_id] = item
            self.on_registered(item)

    def unregister(self, item_id: str) -> None:
        """Unregister an item by its ID."""
        with self._lock:
            if item_id not in self._items:
                raise ItemNotFoundError(f"Item with ID '{item_id}' not found.")
            item = self._items.pop(item_id)
            self.on_unregistered(item)

    def get(self, item_id: str) -> T:
        """Retrieve an item by its ID. Raises ItemNotFoundError if not found."""
        with self._lock:
            if item_id not in self._items:
                raise ItemNotFoundError(f"Item with ID '{item_id}' not found in registry.")
            return self._items[item_id]

    def get_all(self) -> List[T]:
        """Retrieve all registered items as a list."""
        with self._lock:
            return list(self._items.values())

    def exists(self, item_id: str) -> bool:
        """Check if an item exists in the registry."""
        with self._lock:
            return item_id in self._items

    def clear(self) -> None:
        """Clear all registered items from the registry."""
        with self._lock:
            self._items.clear()

    def __iter__(self) -> Iterator[T]:
        """Allows iterating over the registered items directly."""
        with self._lock:
            return iter(list(self._items.values()))

    def __len__(self) -> int:
        """Returns the number of registered items."""
        with self._lock:
            return len(self._items)

    def validate(self, item: T) -> None:
        """Override to implement custom validation constraints."""
        item_id = self._get_item_id(item)
        if not item_id:
            raise ValidationError("Registry items must have a non-empty ID.")

    def _get_item_id(self, item: T) -> str:
        """Helper to extract ID from item."""
        if hasattr(item, 'id'):
            return str(item.id)
        if hasattr(item, 'metadata') and hasattr(item.metadata, 'id'):
            return str(item.metadata.id)
        raise ValidationError("Could not determine ID for registry item.")

    def on_registered(self, item: T) -> None:
        """Hook called after successful registration."""
        pass

    def on_unregistered(self, item: T) -> None:
        """Hook called after successful unregistration."""
        pass
