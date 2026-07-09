from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from backend.knowledge.document_parser import ParsedDocument


@dataclass(slots=True)
class TextChunk:
    document_id: int
    chunk_index: int
    chunk_id: Optional[int] = None
    page_number: Optional[int] = None
    text: str = ""


class Chunker:
    """Split extracted text into semantic chunks.

    Preserves paragraph boundaries and avoids splitting sentences.
    Configurable chunk size and overlap.
    """

    def __init__(self, chunk_size: int = 512, overlap: int = 64) -> None:
        if overlap >= chunk_size:
            raise ValueError("overlap must be smaller than chunk_size")
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, document: ParsedDocument, document_id: int) -> List[TextChunk]:
        chunks: List[TextChunk] = []
        chunk_index = 0

        for page in document.pages:
            paragraphs = self._split_paragraphs(page.text)
            buffer = ""
            buffer_start_paragraph = 0

            for i, para in enumerate(paragraphs):
                if not buffer:
                    buffer_start_paragraph = i

                if len(buffer) + len(para) + 1 <= self._chunk_size:
                    if buffer:
                        buffer += "\n\n"
                    buffer += para
                else:
                    # Flush current buffer as a chunk
                    if buffer:
                        chunks.append(TextChunk(
                            document_id=document_id,
                            chunk_index=chunk_index,
                            page_number=page.page_number,
                            text=buffer.strip(),
                        ))
                        chunk_index += 1

                    # If a single paragraph exceeds chunk_size, hard-split it
                    if len(para) > self._chunk_size:
                        sub_chunks = self._hard_split(para)
                        for sc in sub_chunks:
                            chunks.append(TextChunk(
                                document_id=document_id,
                                chunk_index=chunk_index,
                                page_number=page.page_number,
                                text=sc.strip(),
                            ))
                            chunk_index += 1
                        buffer = ""
                    else:
                        buffer = para
                        buffer_start_paragraph = i

            # Flush remaining buffer
            if buffer:
                chunks.append(TextChunk(
                    document_id=document_id,
                    chunk_index=chunk_index,
                    page_number=page.page_number,
                    text=buffer.strip(),
                ))
                chunk_index += 1

        return chunks

    def _split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs, preserving paragraph boundaries."""
        raw = text.split("\n")
        paragraphs: List[str] = []
        current = ""
        for line in raw:
            stripped = line.strip()
            if not stripped:
                if current:
                    paragraphs.append(current)
                    current = ""
            else:
                if current:
                    current += " " + stripped
                else:
                    current = stripped
        if current:
            paragraphs.append(current)
        return paragraphs

    def _hard_split(self, text: str) -> List[str]:
        """Split a long paragraph into smaller chunks, avoiding mid-sentence breaks."""
        sentences = self._split_sentences(text)
        chunks: List[str] = []
        buffer = ""
        for sentence in sentences:
            if len(buffer) + len(sentence) + 1 > self._chunk_size:
                if buffer:
                    chunks.append(buffer)
                # Apply overlap: start new buffer with end of previous
                if self._overlap > 0 and chunks:
                    last_chunk = chunks[-1]
                    overlap_words = last_chunk.split()[-self._overlap:]
                    buffer = " ".join(overlap_words)
                    if buffer:
                        buffer += " "
                else:
                    buffer = ""
                buffer += sentence
            else:
                if buffer:
                    buffer += " "
                buffer += sentence
        if buffer:
            chunks.append(buffer)
        return chunks

    def _split_sentences(self, text: str) -> List[str]:
        """Simple sentence splitting on common punctuation."""
        import re
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]
