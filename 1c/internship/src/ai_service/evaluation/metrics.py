"""Чистые функции метрик качества поиска (task_252).

Модуль намеренно не импортирует ничего из `app`: метрики должны тестироваться
модульными тестами без поднятого сервиса и без установленных ML-зависимостей.
См. `tests/unit/test_retrieval_metrics.py`.

Определения (совпадают с общепринятыми в IR):
  * hit@k    — доля запросов, у которых хотя бы один релевантный документ в топ-k;
  * MRR      — среднее обратных рангов первого релевантного документа;
  * recall@k — средняя доля найденных релевантных документов от их общего числа.
"""
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple


def _expected_set(expected: Iterable[str]) -> Set[str]:
    return {str(item) for item in expected}


def _path_parts(item: str) -> Tuple[str, ...]:
    """Компоненты пути без префиксов `.` и `..`.

    Поиск возвращает путь таким, каким его видит сервис (`KNOWLEDGE_BASE_DIR` может
    быть относительным, абсолютным или смонтированным в контейнере), а в эталонном
    наборе путь записан от корня проекта. Сравнивать такие строки «в лоб» нельзя:
    метрика показывала бы ноль при полностью рабочем поиске.
    """
    normalized = str(item).strip().replace("\\", "/")
    return tuple(part for part in normalized.split("/") if part not in ("", ".", ".."))


def is_same_document(found_item: str, expected_item: str) -> bool:
    """Совпадает ли найденный документ с эталонным (сравнение по хвосту пути)."""
    found_parts, expected_parts = _path_parts(found_item), _path_parts(expected_item)
    if not found_parts or not expected_parts:
        return False
    if found_parts == expected_parts:
        return True
    shorter, longer = sorted((found_parts, expected_parts), key=len)
    if longer[-len(shorter):] == shorter:
        return True
    # Корпус может быть смонтирован в контейнер по другому пути (/data/knowledge_base),
    # поэтому последняя проверка — совпадение имени файла и имени каталога.
    return (len(found_parts) >= 2 and len(expected_parts) >= 2
            and found_parts[-1] == expected_parts[-1]
            and found_parts[-2] == expected_parts[-2])


def first_relevant_rank(found: Sequence[str], expected: Iterable[str]) -> Optional[int]:
    """1-based ранг первого релевантного документа или None, если такого нет."""
    wanted = _expected_set(expected)
    if not wanted:
        raise ValueError("expected_documents пуст: метрика не определена")
    for index, document in enumerate(found, start=1):
        if any(is_same_document(document, item) for item in wanted):
            return index
    return None


def hit_at_k(found: Sequence[str], expected: Iterable[str], k: int) -> bool:
    """Попал ли хотя бы один релевантный документ в первые k результатов."""
    if k <= 0:
        raise ValueError("k должен быть больше нуля")
    return first_relevant_rank(list(found)[:k], expected) is not None


def reciprocal_rank(found: Sequence[str], expected: Iterable[str]) -> float:
    """1 / ранг первого релевантного документа; 0.0, если его нет."""
    rank = first_relevant_rank(found, expected)
    return 1.0 / rank if rank else 0.0


def recall_at_k(found: Sequence[str], expected: Iterable[str], k: int) -> float:
    """Доля релевантных документов, найденных в первых k результатах."""
    if k <= 0:
        raise ValueError("k должен быть больше нуля")
    wanted = _expected_set(expected)
    if not wanted:
        raise ValueError("expected_documents пуст: recall не определён")
    matched = {item for item in wanted
               if any(is_same_document(document, item) for document in list(found)[:k])}
    return len(matched) / len(wanted)


def mean_reciprocal_rank(cases: Sequence[Tuple[Sequence[str], Iterable[str]]]) -> float:
    """MRR по набору пар (найденные документы, ожидаемые документы)."""
    scored = [(list(found), _expected_set(expected)) for found, expected in cases]
    scored = [case for case in scored if case[1]]
    if not scored:
        return 0.0
    return sum(reciprocal_rank(found, expected) for found, expected in scored) / len(scored)


def summarize(pairs: Sequence[Tuple[Sequence[str], Iterable[str]]],
              hit_k: Sequence[int] = (1, 5),
              recall_k: int = 10) -> Dict[str, float]:
    """Сводка метрик по набору пар.

    Пары с пустым `expected` пропускаются (счётчик `skipped`): вопрос без эталона
    не может участвовать в метриках.
    """
    scored: List[Tuple[List[str], Set[str]]] = []
    for found, expected in pairs:
        wanted = _expected_set(expected)
        if wanted:
            scored.append((list(found), wanted))

    total = len(scored)
    report: Dict[str, float] = {"cases": total, "skipped": len(pairs) - total}

    for k in hit_k:
        hits = sum(1 for found, expected in scored if hit_at_k(found, expected, k))
        report[f"hit@{k}"] = round(hits / total, 3) if total else 0.0

    report["mrr"] = round(sum(reciprocal_rank(found, expected) for found, expected in scored) / total, 3) if total else 0.0
    report[f"recall@{recall_k}"] = round(
        sum(recall_at_k(found, expected, recall_k) for found, expected in scored) / total, 3) if total else 0.0
    return report
