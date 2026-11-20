#!/usr/bin/env python3
"""Зеркальные проверки проведения task_21/22 (документы -> движения -> остатки).

Повторяет логику ОбработкаПроведения поступления и перемещения:
приход/расход, услуги пропускаются, пустая ТЧ не проводится,
движения — в базовых единицах (коэффициент упаковки, task_24).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_posting.py
"""

from __future__ import annotations

from decimal import Decimal

D = Decimal


class PostingError(Exception):
    pass


def receipt_movements(doc: dict) -> list[dict]:
    if not doc["lines"]:
        raise PostingError("пустая табличная часть не проводится")
    moves = []
    for line in doc["lines"]:
        if line.get("is_service"):
            continue
        coef = line.get("pack_coef", D(1))
        moves.append({
            "kind": "Приход",
            "warehouse": doc["warehouse"],
            "product": line["product"],
            "qty": line["qty"] * coef,
        })
    return moves


def transfer_movements(doc: dict) -> list[dict]:
    if not doc["lines"]:
        raise PostingError("пустая табличная часть не проводится")
    moves = []
    for line in doc["lines"]:
        if line.get("is_service"):
            continue
        qty = line["qty"] * line.get("pack_coef", D(1))
        moves.append({"kind": "Расход", "warehouse": doc["from"], "product": line["product"], "qty": qty})
        moves.append({"kind": "Приход", "warehouse": doc["to"], "product": line["product"], "qty": qty})
    return moves


def balances(movements: list[dict]) -> dict:
    result: dict[tuple, Decimal] = {}
    for m in movements:
        key = (m["warehouse"], m["product"])
        delta = m["qty"] if m["kind"] == "Приход" else -m["qty"]
        result[key] = result.get(key, D(0)) + delta
    return result


def check(name: str, actual, expected) -> None:
    assert actual == expected, f"{name}: ожидалось {expected!r}, получено {actual!r}"
    print(f"[ok] {name}")


def main() -> None:
    doc1 = {"warehouse": "РЦ", "lines": [{"product": "Молоко", "qty": D(10), "price": D("50")}]}
    doc2 = {"warehouse": "РЦ", "lines": [{"product": "Молоко", "qty": D(5)}, {"product": "Хлеб", "qty": D(7)}]}
    doc3 = {"warehouse": "Магазин", "lines": [{"product": "Доставка", "qty": D(1), "is_service": True},
                                              {"product": "Молоко", "qty": D(2)}]}
    moves = receipt_movements(doc1) + receipt_movements(doc2) + receipt_movements(doc3)
    bal = balances(moves)
    check("остаток РЦ/Молоко после 2 поступлений", bal[("РЦ", "Молоко")], D(15))
    check("услуга не даёт движения", ("Магазин", "Доставка") in bal, False)

    # пустая ТЧ не проводится
    try:
        receipt_movements({"warehouse": "РЦ", "lines": []})
        raise AssertionError("пустой документ проведён")
    except PostingError:
        print("[ok] пустая ТЧ: проведение запрещено")

    # отмена проведения = движения документа удалены
    bal_after_cancel = balances(receipt_movements(doc2) + receipt_movements(doc3))
    check("после отмены док.1 остаток РЦ/Молоко", bal_after_cancel[("РЦ", "Молоко")], D(5))

    # перемещение: расход+приход, итог по товару не меняется
    transfer = {"from": "РЦ", "to": "Магазин", "lines": [{"product": "Молоко", "qty": D(4)}]}
    bal2 = balances(moves + transfer_movements(transfer))
    check("перемещение: РЦ/Молоко", bal2[("РЦ", "Молоко")], D(11))
    check("перемещение: Магазин/Молоко", bal2[("Магазин", "Молоко")], D(6))

    # упаковка 12 шт: движение в базовых единицах (task_24)
    packed = {"warehouse": "РЦ", "lines": [{"product": "Сок", "qty": D(2), "pack_coef": D(12)}]}
    check("упаковка x12 -> базовые", receipt_movements(packed)[0]["qty"], D(24))


if __name__ == "__main__":
    main()
