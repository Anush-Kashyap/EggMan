from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import logging

from backend.knowledge.loaders.base_loader import BaseDocumentLoader
from backend.knowledge.loaders.pdf_loader import PDFLoader

logger = logging.getLogger("eggman")


class DocumentManager:
    """Orchestrates document loaders and handles raw file text extraction."""

    def __init__(self) -> None:
        self._loaders: Dict[str, BaseDocumentLoader] = {}
        # Automatically register default PDF loader
        self.register_loader(PDFLoader())

    def register_loader(self, loader: BaseDocumentLoader) -> None:
        """Register a document loader for its supported extensions."""
        for ext in loader.supported_extensions():
            ext_lower = ext.lower().strip()
            if not ext_lower.startswith("."):
                ext_lower = f".{ext_lower}"
            self._loaders[ext_lower] = loader
            logger.info("DocumentManager: registered loader %s for extension %s", loader.__class__.__name__, ext_lower)

    def ingest(self, file_path: Path) -> str:
        """Extract text from the file at file_path using the matching registered loader."""
        ext = file_path.suffix.lower()
        loader = self._loaders.get(ext)
        if not loader:
            raise ValueError(f"Unsupported file type: {ext}")
        return loader.load(file_path)

    def supported_extensions(self) -> List[str]:
        """Return a list of all registered/supported file extensions."""
        return list(self._loaders.keys())
