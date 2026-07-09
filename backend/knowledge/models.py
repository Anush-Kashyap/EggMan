from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class KBDocument:
    """Represents an uploaded document in the Knowledge Base."""
    id: Optional[int]
    filename: str
    file_type: str          # "pdf", "txt", "docx", etc.
    file_size: int           # bytes
    content: str             # extracted full text
    source_path: str         # original file path
    created_at: str
    status: str = "indexed"  # waiting, parsing, chunking, embedding, indexed, failed
    chunk_count: int = 0
    metadata: str = "{}"     # JSON string for extensibility
