#!/usr/bin/env python3
"""Проверки алгоритмов task_14 (коллекции) — зеркало BSL-логики на Python.

Платформы 1С в окружении нет, поэтому проверки функций
СгруппироватьПоСвойству / НайтиДубликаты из РИХ_ОбщегоНазначения выполнены
на алгоритмическом зеркале (те же ветвления и сложность). В task_52 эти
проверки переедут в тестовый каркас 1С как есть по кейсам.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_collections.py
"""

from __future__ import annotations

import random
import time


def group_by(rows: list[dict], column: str) -> dict:
    groups: dict = {}
    for row in rows:
        groups.setdefault(row[column], []).append(row)
    return groups


def find_duplicates(items: list) -> list:
    seen: set = set()
    already: set = set()
    result: list = []
    for item in items:
        if item not in seen:
            seen.add(item)
        elif item not in already:
            already.add(item)
            result.append(item)
    return result


def find_duplicates_naive(items: list) -> list:
    result: list = []
    for i, item in enumerate(items):
        if item in items[:i] and item not in result:
            result.append(item)
    return result


def check(name: str, actual, expected) -> None:
    assert actual == expected, f"{name}: ожидалось {expected!r}, получено {actual!r}"
    print(f"[ok] {name}")


def main() -> None:
    rows = [
        {"sku": "A", "qty": 1},
        {"sku": "B", "qty": 2},
        {"sku": "A", "qty": 3},
    ]
    # 3 проверки СгруппироватьПоСвойству
    grouped = group_by(rows, "sku")
    check("группировка: ключи", sorted(grouped), ["A", "B"])
    check("группировка: размер группы A", len(grouped["A"]), 2)
    check("группировка: порядок внутри группы", [r["qty"] for r in grouped["A"]], [1, 3])

    # 3 проверки НайтиДубликаты
    check("дубли: базовый случай", find_duplicates([1, 2, 2, 3, 1]), [2, 1])
    check("дубли: пустой ввод", find_duplicates([]), [])
    check("дубли: без дублей", find_duplicates([1, 2, 3]), [])

    # Замер на 100 000: наивный O(n^2) против эффективного O(n)
    random.seed(42)
    data = [random.randrange(90_000) for _ in range(100_000)]
    start = time.perf_counter()
    fast = find_duplicates(data)
    fast_time = time.perf_counter() - start
    sample = data[:5_000]  # наивный на полном объёме — минуты; меряем на срезе
    start = time.perf_counter()
    find_duplicates_naive(sample)
    naive_sample = time.perf_counter() - start
    print(f"эффективный (100 000): {fast_time:.3f} с, дублей найдено {len(fast)}")
    print(
        f"наивный (срез 5 000): {naive_sample:.3f} с "
        f"-> оценка на 100 000: x{(100_000/5_000)**2:.0f} по времени (~{naive_sample*400:.0f} с)"
    )


if __name__ == "__main__":
    main()
