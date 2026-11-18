"""Поиск и ранжирование (task_238, task_239, task_245)."""
from typing import Dict, List, Optional

from .config import get_settings
from .embeddings import embed_text
from .schemas import Source
from .vectorstore import get_store


def retrieve(query: str, top_k: Optional[int] = None,
             filters: Optional[Dict[str, str]] = None) -> List[Source]:
    """Возвращает top-K релевантных фрагментов с оценкой близости."""
    settings = get_settings()
    top_k = top_k or settings.search_top_k
    store = get_store()

    if store.count() == 0:
        store.rebuild(full=True)

    query_vector = embed_text(query)
    hits = store.search(query_vector, top_k=top_k, filters=filters or {})

    results: List[Source] = []
    for hit in hits:
        chunk = hit["item"].chunk
        score = float(hit["score"])
        if score < settings.search_min_score:
            # task_243: порог релевантности — честный отказ лучше уверенной выдумки.
            continue
        results.append(
            Source(
                document=chunk.document,
                section=chunk.section,
                version=chunk.version,
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                score=round(score, 4),
            )
        )

    if settings.search_hybrid_enabled:
        # task_239: объединение с ключевым (BM25/полнотекстовым) поиском.
        raise NotImplementedError("Гибридный поиск реализуется в задании task_239")
    return results
