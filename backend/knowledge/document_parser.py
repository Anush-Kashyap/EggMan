from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Tuple

from backend.knowledge.document_manager import DocumentManager


@dataclass(slots=True)
class ParsedPage:
    page_number: int
    text: str


@dataclass(slots=True)
class ParsedDocument:
    pages: List[ParsedPage] = field(default_factory=list)

    @property
    def total_pages(self) -> int:
        return len(self.pages)

    @property
    def full_text(self) -> str:
        return "\n".join(p.text for p in self.pages)


class DocumentParser:
    """Responsible only for extracting text from supported files with page info."""

    def __init__(self, document_manager: DocumentManager) -> None:
        self._document_manager = document_manager

    def parse(self, file_path: Path) -> ParsedDocument:
        ext = file_path.suffix.lower()
        loader = self._document_manager._loaders.get(ext)
        if loader is None:
            raise ValueError(f"Unsupported file type: {ext}")

        # Prefer load_pages() if the loader supports it
        load_pages = getattr(loader, "load_pages", None)
        if load_pages is not None:
            raw_pages: List[Tuple[int, str]] = load_pages(file_path)
            pages = [ParsedPage(page_number=pnum, text=text) for pnum, text in raw_pages]
        else:
            text = loader.load(file_path)
            pages = [ParsedPage(page_number=1, text=text)]

        return ParsedDocument(pages=pages)
