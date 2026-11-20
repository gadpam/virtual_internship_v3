#!/usr/bin/env python3
"""Проверки task_100: миграция грязного источника 100 000 позиций (зеркало).

Категории качества сопоставления считаются по первому вхождению
уникального нормализованного артикула: точно / имя разошлось /
похоже на перекодировку / новая / дубль / брак (пустой артикул).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_migration.py
"""

from __future__ import annotations

import random
import time


def norm(article: str) -> str:
    return "".join(article.upper().split()).replace("-", "")


def build_source() -> list[tuple[str, str]]:
    target = {f"SKU{i:05d}": f"Товар эталонный {i}" for i in range(1, 2001)}
    rows: list[tuple[str, str]] = []
    skus = list(target)
    rows += [(sku, target[sku]) for sku in skus[:1500]]                    # точные
    rows += [(sku, target[sku] + " (переим.)") for sku in skus[1500:]]     # имя разошлось
    rows += [(f"OLD{i:05d}", f"Товар эталонный {(i - 1) % 2000 + 1}")
             for i in range(1, 8001)]                                      # перекодировки
    rows += [(f"NEW{i:05d}", f"Новая позиция {i}") for i in range(1, 12001)]
    rng = random.Random(42)
    pool = rows[:]
    rows += [pool[rng.randrange(len(pool))] for _ in range(73_000)]        # дубли
    rows += [("", "Без артикула")] * 5_000                                  # брак
    rng.shuffle(rows)
    return rows


TARGET = {f"SKU{i:05d}": f"Товар эталонный {i}" for i in range(1, 2001)}
TARGET_BY_NORM = {norm(k): k for k in TARGET}
TARGET_NAMES = set(TARGET.values())


def main() -> None:
    rows = build_source()
    assert len(rows) == 100_000, len(rows)

    start = time.perf_counter()
    report = {"exact": 0, "renamed_manual": 0, "recoded_manual": 0,
              "new": 0, "duplicates": 0, "rejected": 0}
    seen: set[str] = set()
    loaded = 0
    for article, name in rows:
        key = norm(article)
        if not key:
            report["rejected"] += 1
            continue
        if key in seen:
            report["duplicates"] += 1
            continue
        seen.add(key)
        if key in TARGET_BY_NORM:
            if TARGET[TARGET_BY_NORM[key]] == name:
                report["exact"] += 1
                loaded += 1
            else:
                report["renamed_manual"] += 1
        elif name in TARGET_NAMES:
            report["recoded_manual"] += 1
        else:
            report["new"] += 1
            loaded += 1
    seconds = time.perf_counter() - start

    manual = report["renamed_manual"] + report["recoded_manual"]
    assert sum(report.values()) == 100_000, report
    print(f"[ok] миграция 100000 за {seconds:.1f} с: {report}")
    print(f"[ok] перенесено без ручной работы: {loaded}; дублей отброшено: {report['duplicates']}")
    print(f"[ok] ручная проверка: {manual} позиций ≈ {manual / 30:.0f} чел.-часов "
          f"(30 позиций/час) — цифра для плана миграции, а не для отчёта «всё хорошо»")


if __name__ == "__main__":
    main()
