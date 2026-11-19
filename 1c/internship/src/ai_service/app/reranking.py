"""Переранжирование выдачи (task_245).

Заготовка интерфейса: реализация (кросс-энкодер / LLM-rerank / эвристика по терминам)
появляется в задании task_245 вместе со сравнением метрик из evaluation/.
"""
from typing import List

from .schemas import Source


def rerank(query: str, sources: List[Source], top_k: int | None = None) -> List[Source]:
    """Переставляет источники по релевантности. Сейчас — стабилизированный passthrough."""
    ordered = sorted(sources, key=lambda s: s.score, reverse=True)
    return ordered[:top_k] if top_k else ordered


def lexical_boost(query: str, source: Source) -> float:
    """Эвристика для гибридного ранжирования: доля терминов запроса во фрагменте."""
    query_tokens = {t for t in query.lower().split() if len(t) > 2}
    if not query_tokens:
        return 0.0
    text_tokens = set(source.text.lower().split())
    matched = len(query_tokens & text_tokens)
    return matched / len(query_tokens)
