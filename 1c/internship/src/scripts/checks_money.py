#!/usr/bin/env python3
"""Проверки task_16 (деньги) — зеркало РаспределитьСумму/СуммаВД/СуммаБезНДС.

Деньги считаем Decimal с округлением HALF_UP (как Окр() в 1С: 0.5 — вверх
по модулю). Кейсы переедут в каркас 1С в task_52.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_money.py
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal


def okr(value: Decimal, digits: int) -> Decimal:
    return value.quantize(Decimal(1).scaleb(-digits), rounding=ROUND_HALF_UP)


def distribute(total: Decimal, weights: list[Decimal], digits: int) -> list[Decimal]:
    parts = [Decimal(0)] * len(weights)
    weight_sum = sum(weights)
    if weight_sum == 0:
        if total == 0:
            return parts
        raise ValueError("сумма весов нулевая при ненулевой сумме")
    biggest = max(range(len(weights)), key=lambda i: weights[i])
    distributed = Decimal(0)
    for i, weight in enumerate(weights):
        if i == biggest:
            continue
        parts[i] = okr(total * weight / weight_sum, digits)
        distributed += parts[i]
    parts[biggest] = total - distributed
    return parts


def with_vat(without: Decimal, rate: Decimal) -> Decimal:
    return okr(without * (100 + rate) / 100, 2)


def without_vat(with_: Decimal, rate: Decimal) -> Decimal:
    return okr(with_ * 100 / (100 + rate), 2)


def check(name: str, actual, expected) -> None:
    assert actual == expected, f"{name}: ожидалось {expected!r}, получено {actual!r}"
    print(f"[ok] {name}")


D = Decimal


def main() -> None:
    # 10 кейсов распределения: сумма частей обязана сходиться ровно
    cases = [
        (D("100"), [1, 1, 1], 2, [D("33.34"), D("33.33"), D("33.33")]),
        (D("0.01"), [1, 1], 2, [D("0.00"), D("0.01")]),
        (D("0"), [1, 1, 1], 2, [D("0"), D("0"), D("0")]),
        (D("1000"), [1], 2, [D("1000")]),
        (D("100"), [0, 0, 5], 2, [D("0"), D("0"), D("100")]),
        (D("10.005"), [1, 1], 3, None),  # количество с точностью 3
        (D("99.99"), [2, 3, 5], 2, None),
        (D("1234.56"), [1, 2, 3, 4], 2, None),
        (D("5"), [1, 1, 1, 1, 1, 1, 1], 2, None),
        (D("0.03"), [1, 1, 1], 2, [D("0.01"), D("0.01"), D("0.01")]),
    ]
    for idx, (total, weights, digits, expected) in enumerate(cases, 1):
        parts = distribute(total, [D(w) for w in weights], digits)
        assert sum(parts) == total, f"кейс {idx}: сумма частей {sum(parts)} != {total}"
        if expected is not None:
            check(f"распределение кейс {idx}", parts, expected)
        else:
            print(f"[ok] распределение кейс {idx}: сходится ровно ({parts})")

    # НДС: 1234.56 с налогом 20% -> без налога 1028.80, налог 205.76
    check("СуммаБезНДС(1234.56, 20)", without_vat(D("1234.56"), D(20)), D("1028.80"))
    check("налог внутри 1234.56", D("1234.56") - without_vat(D("1234.56"), D(20)), D("205.76"))
    check("СуммаВД(1028.80, 20) обратно", with_vat(D("1028.80"), D(20)), D("1234.56"))
    check("СуммаВД ставка 0", with_vat(D("100"), D(0)), D("100.00"))


if __name__ == "__main__":
    main()
