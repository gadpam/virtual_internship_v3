#!/usr/bin/env python3
"""Проверки task_113: пересечения расписания до и после разнесения.

Симуляция ночного окна: тяжёлые задания (граница, сверка, очистка)
до оптимизации стартуют в одну минуту, после — разнесены цепочкой.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_schedule.py
"""

from __future__ import annotations


def peak_concurrency(tasks: list[tuple[str, int, int]]) -> int:
    """tasks: (имя, старт_минута, длительность). Пик одновременных тяжёлых."""
    timeline = [0] * (24 * 60)
    for _, start, duration in tasks:
        for minute in range(start, start + duration):
            timeline[minute] += 1
    return max(timeline)


def main() -> None:
    before = [("граница", 180, 10), ("сверка", 180, 15), ("очистка", 180, 5)]
    after = [("граница", 60, 10), ("сверка", 180, 15), ("очистка", 220, 5)]
    peak_before = peak_concurrency(before)
    peak_after = peak_concurrency(after)
    assert peak_before == 3 and peak_after == 1, (peak_before, peak_after)
    print(f"[ok] пиковая одновременность тяжёлых: до {peak_before}, после {peak_after}")

    chain = [name for name, _, _ in sorted(after, key=lambda t: t[1])]
    assert chain == ["граница", "сверка", "очистка"]
    print(f"[ok] цепочка зависимостей ночного окна: {' → '.join(chain)}")


if __name__ == "__main__":
    main()
