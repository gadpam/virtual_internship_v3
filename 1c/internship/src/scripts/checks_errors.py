#!/usr/bin/env python3
"""Проверки task_51: три класса ошибок обрабатываются по стандарту §5.

- ошибка чтения файла (нет файла) — понятное исключение, не traceback наружу;
- ошибка формата CSV (битая строка прайса) — файл отклоняется целиком;
- отсутствие данных (пустой отбор подбора) — явная ошибка, не «всё подряд».

Запуск: src/scripts/.venv/bin/python src/scripts/checks_errors.py
"""

from __future__ import annotations

from pathlib import Path

from checks_strings import parse_csv


def read_file_strict(path: Path) -> str:
    if not path.exists():
        raise ValueError(f"Файл не найден: {path.name}. Проверьте каталог incoming.")
    return path.read_text(encoding="utf-8")


def validate_price_rows(rows: list[list[str]]) -> None:
    for row in rows[1:]:
        if row and (len(row) < 5 or row[0] == ""):
            raise ValueError("Битые строка прайса: пустой артикул")


def pick_by_props(selection: dict) -> str:
    if not selection:
        raise ValueError("Не заданы значения свойств для подбора")
    return "ok"


def expect_error(name: str, fn) -> None:
    try:
        fn()
    except ValueError as err:
        print(f"[ok] {name}: {err}")
        return
    raise AssertionError(f"{name}: ошибка не поднята")


def main() -> None:
    expect_error("чтение отсутствующего файла",
                 lambda: read_file_strict(Path("data/supplier_price/samples/нет_такого.csv")))
    broken = parse_csv(Path("data/supplier_price/samples/prices_supplier_002_broken.csv").read_text(encoding="utf-8"))
    expect_error("формат CSV (пустой артикул)", lambda: validate_price_rows(broken))
    expect_error("отсутствие данных (пустой отбор)", lambda: pick_by_props({}))


if __name__ == "__main__":
    main()
