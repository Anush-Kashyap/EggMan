from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from backend.memory.models import MemoryRecord
from core.paths import _path


# TODO: Future milestone tasks:
# 1. Integrate ChromaDB/VectorStore fully into the memory manager.
# 2. Replace keyword-based lookup with vector similarity search.
# 3. Use local Ollama embeddings (e.g., nomic-embed-text) for computing vectors.
class VectorStore(Protocol):
    """Provider-independent interface for a vector-capable memory store."""

    def add(self, memory: MemoryRecord, embedding: List[float]) -> None:
        ...

    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        ...


class ChromaVectorStore:
    """Persistent ChromaDB-backed vector store for semantic memory retrieval."""

    def __init__(self, persist_directory: Optional[Path | str] = None) -> None:
        try:
            import chromadb
            from chromadb.config import Settings
        except ImportError as exc:
            raise RuntimeError("ChromaDB vector storage is unavailable; install chromadb to enable vector search.") from exc

        self._persist_directory = Path(persist_directory) if persist_directory is not None else Path(_path("data", "chromadb"))
        self._persist_directory.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self._persist_directory), settings=Settings(anonymized_telemetry=False))
        self._collection = self._client.get_or_create_collection(name="eggman_memories")

    def add(self, memory: MemoryRecord, embedding: List[float]) -> None:
        self._collection.add(
            embeddings=[embedding],
            documents=[memory.value],
            metadatas=[{"memory_id": memory.id, "category": memory.category.value, "key": memory.key}],
            ids=[str(memory.id or f"mem-{abs(hash(memory.value))}")],
        )

    def search(self, query_embedding: List[float], limit: int = 5) -> List[Dict[str, Any]]:
        results = self._collection.query(query_embeddings=[query_embedding], n_results=limit)
        return [
            {
                "memory_id": item,
                "distance": float(distance),
                "metadata": metadata,
                "document": document,
            }
            for item, distance, metadata, document in zip(
                results.get("ids", [[]])[0],
                results.get("distances", [[]])[0],
                results.get("metadatas", [[]])[0],
                results.get("documents", [[]])[0],
            )
        ]


class InMemoryVectorStore(ChromaVectorStore):
    """Backward-compatible alias for the persistent Chroma-backed store."""

    def __init__(self, persist_directory: Optional[Path | str] = None) -> None:
        super().__init__(persist_directory=persist_directory)
