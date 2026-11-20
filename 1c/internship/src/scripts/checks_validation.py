#!/usr/bin/env python3
"""Зеркальные проверки task_38 — логика модуля РИХ_Валидация (8+ кейсов).

Кейсы уедут в тестовый каркас 1С в task_52 первым покрытием модуля.
Запуск: src/scripts/.venv/bin/python src/scripts/checks_validation.py
"""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

D = Decimal


def qty_positive(qty) -> bool:
    return qty > 0


def date_not_future(moment: datetime, now: datetime) -> bool:
    end_today = now.replace(hour=23, minute=59, second=59)
    return moment <= end_today


def warehouse_ok(wh) -> bool:
    return bool(wh) and not wh.get("deleted", False)


def not_service(product) -> bool:
    return bool(product) and not product.get("is_service", False)


def receipt_errors(doc: dict, now: datetime) -> list[dict]:
    errors = []
    if not warehouse_ok(doc["warehouse"]):
        errors.append({"field": "Склад", "text": "Склад не выбран или помечен на удаление"})
    if not date_not_future(doc["date"], now):
        errors.append({"field": "Дата", "text": "Дата документа в будущем"})
    for i, line in enumerate(doc["lines"]):
        if not not_service(line["product"]):
            errors.append({"field": f"Товары[{i}].Номенклатура", "text": "Услугу нельзя оприходовать"})
        if not qty_positive(line["qty"]):
            errors.append({"field": f"Товары[{i}].Количество", "text": "Количество должно быть больше нуля"})
    return errors


def check(name: str, actual, expected) -> None:
    assert actual == expected, f"{name}: ожидалось {expected!r}, получено {actual!r}"
    print(f"[ok] {name}")


def main() -> None:
    now = datetime(2026, 11, 17, 12, 0)
    good = {
        "warehouse": {"deleted": False},
        "date": now,
        "lines": [{"product": {"is_service": False}, "qty": D(3)}],
    }
    check("валидный документ: ошибок нет", receipt_errors(good, now), [])
    check("количество 0", qty_positive(D(0)), False)
    check("количество отрицательное", qty_positive(D(-1)), False)
    check("количество положительное", qty_positive(D("0.001")), True)
    check("дата завтра", date_not_future(now + timedelta(days=1, hours=13), now), False)
    check("дата сегодня вечером", date_not_future(now.replace(hour=23), now), True)
    check("склад помечен на удаление", warehouse_ok({"deleted": True}), False)
    check("склад не выбран", warehouse_ok(None), False)
    check("услуга не товар", not_service({"is_service": True}), False)

    bad = {
        "warehouse": None,
        "date": now + timedelta(days=2),
        "lines": [
            {"product": {"is_service": True}, "qty": D(0)},
            {"product": {"is_service": False}, "qty": D(-2)},
        ],
    }
    errors = receipt_errors(bad, now)
    check("сводка: все ошибки сразу (5)", len(errors), 5)
    check("сводка: поля привязаны", [e["field"] for e in errors],
          ["Склад", "Дата", "Товары[0].Номенклатура", "Товары[0].Количество", "Товары[1].Количество"])


if __name__ == "__main__":
    main()
