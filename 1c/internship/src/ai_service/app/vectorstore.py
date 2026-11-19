"""Векторный индекс (task_237).

Бэкенды:
- memory  — список векторов и точный перебор (рабочая заготовка, хорош до ~100k фрагментов);
- faiss   — приближённый индекс (подключается в task_237);
- pgvector — индекс в вашем PostgreSQL (подключается в task_237).

Версии индекса и корпуса хранятся явно: это требование task_240.
"""
import math
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .chunking import Chunk, build_chunks
from .config import get_settings
from .embeddings import embed_text


@dataclass
class StoredChunk:
    chunk: Chunk
    vector: List[float] = field(default_factory=list)


class MemoryVectorStore:
    """Точный перебор по косинусной близости. Простой, воспроизводимый, без зависимостей."""

    def __init__(self) -> None:
        self._items: List[StoredChunk] = []
        self._corpus_version: Optional[str] = None
        self._built_at: Optional[float] = None

    def rebuild(self, full: bool = True) -> Dict[str, object]:
        settings = get_settings()
        started = time.perf_counter()
        chunks: List[Chunk] = build_chunks()
        self._items = [StoredChunk(chunk=c, vector=embed_text(c.text)) for c in chunks]
        self._corpus_version = f"{len(chunks)}-chunks"
        self._built_at = time.time()
        return {
            "vectors": self.count(),
            "documents": self.documents_count(),
            "corpus_version": self._corpus_version,
            "backend": settings.vector_backend,
            "took_ms": int((time.perf_counter() - started) * 1000),
        }

    def count(self) -> int:
        return len(self._items)

    def documents_count(self) -> int:
        return len({item.chunk.document for item in self._items})

    def corpus_version(self) -> Optional[str]:
        return self._corpus_version

    def search(self, query_vector: List[float], top_k: int = 5,
               filters: Optional[Dict[str, str]] = None) -> List[Dict[str, object]]:
        results = []
        for item in self._items:
            if filters and not _matches(item.chunk, filters):
                continue
            results.append({"item": item, "score": cosine(query_vector, item.vector)})
        results.sort(key=lambda r: r["score"], reverse=True)
        return results[:top_k]


def _matches(chunk: Chunk, filters: Dict[str, str]) -> bool:
    """Фильтр по метаданным ДО векторного поиска (см. подсказку в task_237)."""
    checks = {
        "document": chunk.document,
        "section": chunk.section,
        "version": chunk.version,
    }
    return all(str(checks.get(key, "")) == str(value) for key, value in filters.items())


def cosine(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a)) or 1.0
    norm_b = math.sqrt(sum(y * y for y in b)) or 1.0
    score = dot / (norm_a * norm_b)
    return max(0.0, min(1.0, (score + 1.0) / 2.0))


_store: Optional[MemoryVectorStore] = None


def get_store() -> MemoryVectorStore:
    """Единая точка доступа к индексу (в task_237 здесь появится выбор бэкенда)."""
    global _store
    if _store is None:
        settings = get_settings()
        if settings.vector_backend != "memory":
            # faiss / pgvector подключаются в задании task_237.
            raise NotImplementedError(
                f"Бэкенд '{settings.vector_backend}' подключается в задании task_237"
            )
        _store = MemoryVectorStore()
    return _store
