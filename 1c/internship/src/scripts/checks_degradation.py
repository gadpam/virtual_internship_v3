#!/usr/bin/env python3
"""Проверки task_131: учение по деградации (зеркало).

Сценарий субботнего полдня: лояльность и ТК лежат (fault 500),
курсы банка недоступны. Продажа проходит в ограниченном режиме:
бонусы уходят в отложенную очередь с баннером покупателю, доставка
считается по сетке с пометкой «оценка», курс берётся последний
известный с его датой. После восстановления очередь расходится
без дублей. Отдельно: продажа с неизвестными остатками — стоп,
а не деградация (честный отказ лучше тихой неполноценности).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_degradation.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta

LOYALTY = "http://127.0.0.1:8021"
LOYALTY_KEY = "mock-loyalty-key"
TK = "http://127.0.0.1:8022"
TK_KEY = os.environ.get("MOCK_TK_API_KEY", "mock-tk-key")
BANNER_LOYALTY = ("Бонусы временно не начисляются при покупке: начислим "
                  "автоматически после восстановления сервиса")
BANNER_TK = "Стоимость доставки — предварительная оценка"
GRID = {"Минск": 7.0, "Гродно": 12.0, "Брест": 12.0}


def call(base: str, key: str, method: str, path: str,
         body: dict | None = None, fault: str | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(base + path, method=method)
    req.add_header("X-Api-Key", key)
    if fault:
        req.add_header("X-Fault-Mode", fault)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


class DeferredQueue:
    """Зеркало ОчередиОбмена для отложенных операций деградации."""

    def __init__(self) -> None:
        self.items: list[dict] = []

    def put(self, operation: dict) -> None:
        if any(item["operation_id"] == operation["operation_id"] for item in self.items):
            return
        self.items.append(operation)

    def drain(self) -> int:
        done = 0
        remaining = []
        for item in self.items:
            code, _ = call(LOYALTY, LOYALTY_KEY, "POST", "/api/v1/accrue", item)
            if code in (200, 201):
                done += 1
            else:
                remaining.append(item)
        self.items = remaining
        return done


def balance(card: str) -> float:
    _, data = call(LOYALTY, LOYALTY_KEY, "GET", f"/api/v1/cards/{card}/balance")
    return data["balance"]


def degraded_accrue(queue: DeferredQueue, op: dict, partner_down: bool) -> dict:
    if not partner_down:
        code, _ = call(LOYALTY, LOYALTY_KEY, "POST", "/api/v1/accrue", op)
        if code in (200, 201):
            return {"accrued": True, "deferred": False, "banner": ""}
    queue.put(op)
    return {"accrued": False, "deferred": True, "banner": BANNER_LOYALTY}


def degraded_tariff(city: str, partner_down: bool) -> dict:
    if not partner_down:
        code, data = call(TK, TK_KEY, "POST", "/api/v1/calculate",
                          {"city_to": city, "weight_kg": 1, "volume_m3": 0.01})
        if code == 200:
            return {"price": data["price"], "estimate": False, "banner": ""}
    return {"price": GRID.get(city, 15.0), "estimate": True, "banner": BANNER_TK}


def degraded_rate(snapshot: dict, today: date) -> dict:
    age = (today - snapshot["date"]).days
    if age > 7:
        raise RuntimeError(f"RIH-422: курс старше 7 дней ({snapshot['date']}) — стоп")
    return {"rate": snapshot["rate"], "date": snapshot["date"],
            "stale": age > 0}


def sell_with_unknown_stock(stock_known: bool) -> str:
    if not stock_known:
        raise RuntimeError("RIH-STOP: остатки неизвестны — проведение запрещено, "
                           "это не деградация, а честный отказ")
    return "проведено"


def main() -> None:
    suffix = uuid.uuid4().hex[:8]
    card = "CARD-DEG-" + suffix
    queue = DeferredQueue()
    op = {"operation_id": "DEG-" + suffix, "card": card, "points": 100,
          "reason": "покупка в деградации"}
    start = balance(card)

    sale = degraded_accrue(queue, op, partner_down=True)
    assert sale["deferred"] and BANNER_LOYALTY in sale["banner"]
    assert balance(card) == start and len(queue.items) == 1
    print(f"[ok] продажа без бонусов: покупка прошла, начисление отложено, "
          f"покупатель видит баннер, а не тишину")

    tariff = degraded_tariff("Гродно", partner_down=True)
    assert tariff["estimate"] and tariff["price"] == 12.0
    print(f"[ok] доставка без ТК: оценка по сетке {tariff['price']} с пометкой "
          f"«{BANNER_TK}»")

    fresh = degraded_rate({"rate": 3.0, "date": date.today() - timedelta(days=2)},
                          date.today())
    assert fresh["stale"] and fresh["rate"] == 3.0
    try:
        degraded_rate({"rate": 3.0, "date": date.today() - timedelta(days=8)},
                      date.today())
        raise AssertionError("недельный курс принят как деградация")
    except RuntimeError as err:
        print(f"[ok] курс: 2 дня — работаем с датой на виду; 8 дней — {err}")

    drained = queue.drain()
    assert drained == 1 and balance(card) == start + 100 and not queue.items
    again = queue.drain()
    assert again == 0 and balance(card) == start + 100
    print("[ok] восстановление: отложенное начисление выполнено ровно один раз, "
          "повторный прогон очереди дублей не дал")

    try:
        sell_with_unknown_stock(stock_known=False)
        raise AssertionError("продажа с неизвестными остатками прошла")
    except RuntimeError as err:
        print(f"[ok] граница деградации: {err}")
    assert sell_with_unknown_stock(stock_known=True) == "проведено"
    print("[ok] учение пройдено: два сервиса лежат — продажи живы и честны")


if __name__ == "__main__":
    main()
