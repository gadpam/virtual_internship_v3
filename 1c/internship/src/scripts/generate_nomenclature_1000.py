#!/usr/bin/env python3
"""Генератор 1000 позиций номенклатуры для task_20 (загрузочный CSV).

Настоящий генератор тестовых данных появится в task_55; здесь — внешний
файл загрузки для будущей обработки в ИБ. Платформы нет, поэтому «загрузка»
проверяется зеркально: поиск по артикулу меряется сканированием против
словаря-индекса.

Запуск: src/scripts/.venv/bin/python src/scripts/generate_nomenclature_1000.py
"""

from __future__ import annotations

import csv
import random
import time
from pathlib import Path

GROUPS = [
    "Продукты питания/Молочные продукты",
    "Продукты питания/Бакалея",
    "Бытовая химия/Для дома",
    "Продукты питания/Напитки",
]
BASES = ["Молоко", "Кефир", "Хлеб", "Крупа", "Сок", "Мыло", "Сыр", "Йогурт"]


def main() -> None:
    random.seed(20)
    rows = []
    for i in range(1, 1001):
        rows.append(
            {
                "Артикул": f"SKU-{i:05d}",
                "Наименование": f"{random.choice(BASES)} учебный {i}",
                "Группа": random.choice(GROUPS),
                "ЕдиницаИзмерения": "шт",
                "Вес": "0.900",
                "СтавкаНДС": "20",
            }
        )
    path = Path("data/nomenclature_1000.csv")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]), delimiter=";")
        writer.writeheader()
        writer.writerows(rows)
    print(f"записано строк: {len(rows)} -> {path}")

    needle = "SKU-00777"
    start = time.perf_counter()
    found_scan = [r for r in rows if needle in r["Артикул"]]
    scan_ms = (time.perf_counter() - start) * 1000
    index = {r["Артикул"]: r for r in rows}
    start = time.perf_counter()
    found_idx = [index[needle]]
    idx_ms = (time.perf_counter() - start) * 1000
    assert found_scan == found_idx
    print(f"поиск на 1000: сканирование {scan_ms:.2f} мс, словарь {idx_ms:.3f} мс")


if __name__ == "__main__":
    main()
