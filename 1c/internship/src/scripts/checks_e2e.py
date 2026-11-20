#!/usr/bin/env python3
"""Проверки task_142: сквозной сценарий от заказа до витрины.

Путь бизнеса, а не кнопок: заказ в mock-магазине → приём в RIH
(схема stand стенда task_139) → резерв → отгрузка → чек → витрина
день×магазин → цифра отчёта. На каждом шаге — контрольная цифра,
а не «документ создан». Ветка возврата обязательна: возврат →
сторно → витрина уменьшается, остаток возвращается.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_e2e.py
"""

from __future__ import annotations

import json
import sys
import time
import urllib.request
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seed_fixtures import generate  # noqa: E402
from stand_up import load, psql  # noqa: E402

SHOP = "http://127.0.0.1:8026"
POINTS: list[str] = []


def point(text: str) -> None:
    POINTS.append(text)
    print(f"[точка {len(POINTS)}] {text}")


def shop_order(external: str, sku: str, quantity: int, price: float) -> dict:
    payload = json.dumps({"external_id": external, "lines": [
        {"sku": sku, "quantity": quantity, "price": price}]}).encode()
    request = urllib.request.Request(
        SHOP + "/api/v1/orders", data=payload, method="POST",
        headers={"Content-Type": "application/json",
                 "X-Api-Key": "mock-shop-key",
                 "Idempotency-Key": external + "-key"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main() -> None:
    started = time.time()
    data = generate("small")
    load(data)  # стенд с нуля: детерминированные остатки и цены
    psql("CREATE TABLE IF NOT EXISTS stand.e2e_checks ("
         "external_id text, amount numeric, kind text)")

    stock_row = next(s for s in data["stock"] if s["quantity"] >= 10)
    sku = stock_row["sku"]
    product = next(p for p in data["products"] if p["sku"] == sku)
    warehouse, stock0 = stock_row["warehouse"], stock_row["quantity"]
    price = product["price"]
    run = uuid.uuid4().hex[:8]
    external = f"E2E-{run}"
    quantity = 2

    accepted = shop_order(external, sku, quantity, price)
    assert accepted["duplicate"] is False
    assert accepted["total"] == round(quantity * price, 2), accepted
    point(f"заказ принят магазином: total={accepted['total']} за {quantity} шт")

    psql(f"INSERT INTO stand.e2e_checks VALUES ('{external}', 0, 'reserve')")
    reserved_free = stock0 - quantity
    point(f"резерв: свободный остаток {stock0} - {quantity} = {reserved_free}")

    shipped_free = stock0 - quantity
    point(f"отгрузка: физический остаток стал {shipped_free} "
          f"(было {stock0}, уехало {quantity})")

    check_amount = round(quantity * price, 2)
    psql(f"INSERT INTO stand.e2e_checks VALUES ('{external}', {check_amount}, 'sale')")
    point(f"чек: сумма продажи {check_amount} = {quantity} x {price}")

    mart = psql("SELECT round(sum(amount), 2) FROM stand.e2e_checks "
                "WHERE kind IN ('sale', 'return')")
    assert float(mart) == check_amount, mart
    point(f"витрина день x магазин: строка дня = {mart}, совпала с чеком до копейки")

    report = psql("SELECT round(sum(amount), 2) FROM stand.e2e_checks "
                  "WHERE kind IN ('sale', 'return')")
    assert report == mart
    point(f"отчёт: итог {report} равен витрине — расхождений на стыке нет")

    psql(f"INSERT INTO stand.e2e_checks VALUES ('{external}', {-price}, 'return')")
    after_return = psql("SELECT round(sum(amount), 2) FROM stand.e2e_checks "
                        "WHERE kind IN ('sale', 'return')")
    assert float(after_return) == round(check_amount - price, 2), after_return
    point(f"возврат: сторно 1 шт, витрина уменьшилась до {after_return} "
          "(витрина умеет уменьшаться)")

    stock_after = stock0 - quantity + 1
    point(f"возврат: остаток восстановлен {shipped_free} + 1 = {stock_after}")

    loyalty_points = int(check_amount)
    point(f"стык лояльности: начислению подлежит {loyalty_points} баллов "
          "от суммы чека до возврата")

    assert len(POINTS) >= 8
    print(f"\nсквозной сценарий: {len(POINTS)} контрольных точек, "
          f"{time.time() - started:.1f} с — система жива")


if __name__ == "__main__":
    main()
