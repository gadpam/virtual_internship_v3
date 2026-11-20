#!/usr/bin/env python3
"""Зеркальные проверки task_43: контроль остатков при перемещении (5+ кейсов).

Повторяет логику РИХ_УчётТоваровДвижения.ДвиженияПеремещения: контроль
по остатку с уменьшением внутри документа (две строки одного товара).
Кейсы уедут в каркас task_52.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_stock_control.py
"""

from __future__ import annotations

from decimal import Decimal

D = Decimal


class StockError(Exception):
    pass


def transfer(stock: dict, lines: list[dict]) -> list[dict]:
    """stock: {(склад, товар): остаток}; lines: строки перемещения с qty."""
    available = dict(stock)
    moves = []
    for line in lines:
        if line.get("is_service"):
            continue
        key = ("SRC", line["product"])
        avail = available.get(key, D(0))
        if line["qty"] > avail:
            raise StockError(
                f"Недостаточно {line['product']}: доступно {avail}, требуется {line['qty']}"
            )
        moves.append(("Расход", "SRC", line["product"], line["qty"]))
        moves.append(("Приход", "DST", line["product"], line["qty"]))
        available[key] = avail - line["qty"]
    return moves


def check_ok(name: str, stock, lines, expected_moves: int) -> None:
    moves = transfer(stock, lines)
    assert len(moves) == expected_moves, f"{name}: {len(moves)} != {expected_moves}"
    print(f"[ok] {name}")


def check_fail(name: str, stock, lines) -> None:
    try:
        transfer(stock, lines)
    except StockError as err:
        print(f"[ok] {name}: {err}")
        return
    raise AssertionError(f"{name}: превышение не запрещено")


def main() -> None:
    stock = {("SRC", "Молоко"): D(10)}
    check_ok("в пределах остатка", stock, [{"product": "Молоко", "qty": D(10)}], 2)
    check_fail("больше остатка на 1", stock, [{"product": "Молоко", "qty": D(11)}])
    check_fail("товара нет на складе", stock, [{"product": "Хлеб", "qty": D(1)}])
    check_fail(
        "две строки одного товара вместе больше остатка",
        stock,
        [{"product": "Молоко", "qty": D(6)}, {"product": "Молоко", "qty": D(6)}],
    )
    check_ok("услуга не двигается и не контролируется", stock,
             [{"product": "Доставка", "qty": D(99), "is_service": True}], 0)
    check_ok("пустой документ: движений нет", stock, [], 0)


if __name__ == "__main__":
    main()
