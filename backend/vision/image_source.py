from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional


class ImageSource(ABC):
    """Abstract base class representing a source of visual content."""

    @abstractmethod
    def capture(self) -> Optional[bytes]:
        """Capture the visual content and return raw image bytes (PNG/JPEG)."""
        pass
