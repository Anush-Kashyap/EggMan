from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import List


class BaseDocumentLoader(ABC):
    """Abstract base class for document loaders.

    Subclass this to add support for new file types (DOCX, TXT, Markdown, etc.)
    without changing the public API.
    """

    @abstractmethod
    def supported_extensions(self) -> List[str]:
        """Return a list of file extensions this loader handles, e.g. ['.pdf']."""
        ...

    @abstractmethod
    def load(self, file_path: Path) -> str:
        """Extract and return the full text content of the document at *file_path*."""
        ...
