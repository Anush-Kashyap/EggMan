from __future__ import annotations

from collections.abc import Callable
from typing import Dict, Optional

from core.providers import BaseProvider


ProviderFactory = Callable[[], BaseProvider]


class ProviderRegistry:
    """Registry for available AI providers and active provider selection."""

    def __init__(self) -> None:
        self._providers: Dict[str, ProviderFactory] = {}
        self._active_key: Optional[str] = None

    def register(self, key: str, provider_factory: ProviderFactory) -> None:
        self._providers[key] = provider_factory
        if self._active_key is None:
            self._active_key = key

    def get(self, key: Optional[str] = None) -> Optional[ProviderFactory]:
        if key is None:
            key = self._active_key
        return self._providers.get(key)

    def activate(self, key: str) -> bool:
        if key not in self._providers:
            return False
        self._active_key = key
        return True

    def active_provider_name(self) -> Optional[str]:
        return self._active_key

    def available_providers(self) -> list[str]:
        return list(self._providers.keys())
