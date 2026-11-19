"""Эмбеддинги и кеш (task_235, task_240).

Заготовка содержит детерминированный «mock-эмбеддер»: он не понимает смысл,
но позволяет отладить весь конвейер (индекс, поиск, ранжирование) без внешнего API.
В task_235 вы подключите реальную модель или HTTP-провайдер эмбеддингов.
"""
import hashlib
import math
from typing import Dict, List

from .config import get_settings

_cache: Dict[str, List[float]] = {}


def embed_text(text: str) -> List[float]:
    """Возвращает вектор фиксированной размерности (кешируется по тексту)."""
    settings = get_settings()
    key = hashlib.sha256(text.encode("utf-8")).hexdigest()
    if key in _cache:
        return _cache[key]

    if settings.embedding_provider == "mock":
        vector = _mock_vector(text, settings.embedding_dim)
    else:
        # task_235: вызов HTTP-провайдера эмбеддингов.
        # Требования: таймаут, ретраи (task_128), логирование, учет стоимости (task_240).
        raise NotImplementedError("HTTP-провайдер эмбеддингов подключается в задании task_235")

    _cache[key] = vector
    return vector


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Пакетное эмбеддирование: кеш экономит вызовы провайдера (task_240)."""
    return [embed_text(text) for text in texts]


def cache_stats() -> Dict[str, int]:
    return {"cached_vectors": len(_cache)}


def _mock_vector(text: str, dim: int) -> List[float]:
    """Псевдо-эмбеддинг: bag-of-hashed-words.

    Полезен для отладки конвейера и тестов, но НЕ отражает семантику:
    синонимы не будут близки. Это намеренно — в task_235 вы увидите разницу.
    """
    vector = [0.0] * dim
    for token in _tokens(text):
        digest = hashlib.md5(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign
    norm = math.sqrt(sum(v * v for v in vector)) or 1.0
    return [v / norm for v in vector]


def _tokens(text: str) -> List[str]:
    lowered = text.lower()
    return [t for t in "".join(ch if ch.isalnum() or ch.isspace() else " " for ch in lowered).split() if t]
