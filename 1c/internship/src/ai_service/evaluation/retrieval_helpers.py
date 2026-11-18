"""Мост между поиском AI-сервиса и метриками оценки (task_252).

`search_documents` — единственная функция, которой нужен живой индекс; метрики
импортируются из `metrics.py`, чтобы их можно было тестировать изолированно.
"""
import os
import sys
from typing import List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.retrieval import retrieve  # noqa: E402
from metrics import (  # noqa: E402,F401  — реэкспорт для скриптов оценки
    first_relevant_rank,
    hit_at_k,
    mean_reciprocal_rank,
    recall_at_k,
    reciprocal_rank,
    summarize,
)


def search_documents(query: str, top_k: int = 10) -> List[str]:
    """Упорядоченный список документов-источников для вопроса."""
    return [source.document for source in retrieve(query, top_k=top_k)]
