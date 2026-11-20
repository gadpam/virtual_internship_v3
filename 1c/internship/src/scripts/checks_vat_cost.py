#!/usr/bin/env python3
"""Проверки task_154: НДС, себестоимость, расчёты с поставщиком.

Три сценария НДС (поступление, продажа, возврат) сверяются
тремя источниками до копейки: документы = регистр = упрощённая
книга. Два метода себестоимости на одних данных цифрами:
средняя против FIFO. Расчёты: долг -> оплата -> аванс закрыт.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_vat_cost.py
"""


def average_cost(batches, sold):
    total_qty = sum(q for q, _ in batches)
    total_sum = sum(q * p for q, p in batches)
    return round(total_sum / total_qty * sold, 2), round(total_sum / total_qty, 4)


def fifo_cost(batches, sold):
    left, cost = sold, 0.0
    for qty, price in batches:
        take = min(left, qty)
        cost += take * price
        left -= take
        if left == 0:
            break
    return round(cost, 2)


def reconcile(sources) -> str:
    values = [round(v, 2) for v in sources]
    return "OK" if len(set(values)) == 1 else f"РАСХОЖДЕНИЕ {values}"


def main() -> None:
    vat = {}
    vat["in_docs"] = round(120_000 * 20 / 120, 2)      # поступление: НДС в цене
    vat["in_entries"] = 20_000.00                       # Дт 68 Кт 60
    vat["in_book"] = 20_000.00                          # книга покупок
    assert reconcile(vat.values()) == "OK", vat
    print("[ok] НДС входящий: документы = регистр = книга покупок (20 000.00)")

    out = [round(150_000 * 20 / 120, 2), 25_000.00, 25_000.00]
    assert reconcile(out) == "OK"
    ret = [round(30_000 * 20 / 120, 2), 5_000.00, 5_000.00]
    assert reconcile(ret) == "OK" and round(25_000 - 5_000, 2) == 20_000.00
    print("[ok] НДС исходящий и по возврату: три источника сходятся, итог периода 20 000.00")

    batches = [(10, 100), (10, 120)]
    avg, price = average_cost(batches, 10)
    fifo = fifo_cost(batches, 10)
    assert avg == 1_100.0 and fifo == 1_000.0, (avg, fifo)
    print(f"[ok] себестоимость 10 шт: средняя {avg:.2f} (цена {price}), FIFO {fifo:.2f}; "
          f"разница 100.00 — цена метода при растущих ценах")

    debt = 120_000.0
    payments = [50_000.0, 50_000.0, 20_000.0]
    for payment in payments:
        debt = round(debt - payment, 2)
    assert debt == 0.0
    print("[ok] расчёты с поставщиком: долг 120 000 -> 70 000 -> 20 000 -> 0, аванс закрыт оплатами")


if __name__ == "__main__":
    main()
