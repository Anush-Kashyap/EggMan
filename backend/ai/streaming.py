from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator, List, Optional


@dataclass(slots=True)
class StreamChunk:
    """Represents one incremental chunk of a streamed response."""

    text: str
    done: bool = False


class StreamingResponse:
    """Small abstraction that can later be bound to provider streams or Qt signals."""

    def __init__(self, chunks: Optional[Iterable[str]] = None, on_complete: Optional[Callable[[], None]] = None) -> None:
        self._chunks = chunks or []
        self._iterator: Iterator[str] = iter(self._chunks)
        self._on_complete = on_complete

    def __iter__(self):
        return self

    def __next__(self) -> StreamChunk:
        try:
            chunk = next(self._iterator)
        except StopIteration:
            if self._on_complete:
                self._on_complete()
                self._on_complete = None
            raise StopIteration
        return StreamChunk(text=chunk, done=False)

    def with_completion(self, callback: Callable[[], None]) -> "StreamingResponse":
        self._on_complete = callback
        return self


class StreamingPipeline:
    """Provider-agnostic streaming coordinator for future AI backends."""

    def __init__(self, on_chunk: Optional[Callable[[str], None]] = None) -> None:
        self._on_chunk = on_chunk

    def stream(self, text: str) -> StreamingResponse:
        chunks = [part for part in text.split(" ") if part]
        if not chunks:
            chunks = [""]
        return StreamingResponse(chunks=chunks)

    def emit(self, text: str) -> None:
        if self._on_chunk is not None:
            self._on_chunk(text)
