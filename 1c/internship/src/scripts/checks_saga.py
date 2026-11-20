#!/usr/bin/env python3
"""Проверки task_130: сага «резерв → оплата → доставка» и компенсации.

Живые моки: магазин :8026 (заказ и его статус), лояльность :8021
(списание и сторно), ТК :8022 (заявка). Сбой на каждом шаге:
компенсации идут в обратном порядке и видны парами в журнале саги.
Двойная компенсация безопасна. Неудавшаяся компенсация падает
в очередь ручного разбора с алертом, а не «попробуем ночью».

Запуск: src/scripts/.venv/bin/python src/scripts/checks_saga.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid

SHOP = os.environ.get("MOCK_SHOP_URL", "http://127.0.0.1:8026")
SHOP_KEY = os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key")
LOYALTY = "http://127.0.0.1:8021"
LOYALTY_KEY = "mock-loyalty-key"
TK = "http://127.0.0.1:8022"
TK_KEY = os.environ.get("MOCK_TK_API_KEY", "mock-tk-key")


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


class CompensationFailed(Exception):
    pass


class Saga:
    def __init__(self, saga_id: str) -> None:
        self.id = saga_id
        self.done: list[str] = []
        self.journal: list[str] = []
        self.manual_queue: list[dict] = []
        self.card = "CARD-SAGA-" + saga_id[-6:]

    def step_reserve(self) -> None:
        code, _ = call(SHOP, SHOP_KEY, "POST", "/api/v1/orders",
                       {"external_id": self.id, "lines": [
                           {"sku": "SKU-1", "quantity": 1, "price": 100.0}]})
        assert code in (201, 200), code
        code, _ = call(SHOP, SHOP_KEY, "PATCH",
                       f"/api/v1/orders/{self.id}/status?status=reserved")
        assert code == 200, code
        self.done.append("reserve")
        self.journal.append("шаг reserve выполнен")

    def step_payment(self, points: int) -> None:
        code, _ = call(LOYALTY, LOYALTY_KEY, "POST", "/api/v1/redeem",
                       {"operation_id": self.id + "-pay", "card": self.card,
                        "points": points, "reason": "оплата заказа"})
        if code >= 400:
            raise RuntimeError(f"оплата отклонена: {code}")
        self.done.append("payment")
        self.journal.append("шаг payment выполнен")

    def step_delivery(self, fault: str | None = None) -> None:
        code, _ = call(TK, TK_KEY, "POST", "/api/v1/shipments",
                       {"external_id": self.id + "-ship", "city_to": "Минск",
                        "weight_kg": 1}, fault=fault)
        if code >= 400:
            raise RuntimeError(f"доставка отклонена: {code}")
        self.done.append("delivery")
        self.journal.append("шаг delivery выполнен")

    def compensate(self, fail_payment_compensation: bool = False) -> bool:
        ok = True
        for step in reversed(self.done):
            try:
                if step == "payment":
                    code, _ = call(LOYALTY, LOYALTY_KEY, "POST",
                                   f"/api/v1/reverse?operation_id={self.id}-pay",
                                   fault="error500" if fail_payment_compensation else None)
                    if code >= 400 and code != 409:
                        raise CompensationFailed(f"сторно отклонено: {code}")
                elif step == "reserve":
                    code, _ = call(SHOP, SHOP_KEY, "PATCH",
                                   f"/api/v1/orders/{self.id}/status?status=cancelled")
                    if code >= 400:
                        raise CompensationFailed(f"отмена заказа отклонена: {code}")
                self.journal.append(f"компенсация {step} выполнена")
            except CompensationFailed as err:
                ok = False
                self.manual_queue.append({"saga": self.id, "step": step, "reason": str(err)})
                self.journal.append(
                    f"АЛЕРТ оператору: компенсация {step} не удалась ({err}); "
                    f"очередь ручного разбора, в тот же день")
        return ok

    def order_status(self) -> str:
        _, data = call(SHOP, SHOP_KEY, "GET", "/api/v1/orders?limit=1000")
        for item in data.get("items", []):
            if item["externalId"] == self.id:
                return item["status"]
        return "not-found"

    def balance(self) -> int:
        _, data = call(LOYALTY, LOYALTY_KEY, "GET", f"/api/v1/cards/{self.card}/balance")
        return data["balance"]


def fund(saga: Saga, points: int) -> None:
    code, _ = call(LOYALTY, LOYALTY_KEY, "POST", "/api/v1/accrue",
                   {"operation_id": saga.id + "-fund", "card": saga.card,
                    "points": points, "reason": "стартовый баланс стенда"})
    assert code in (200, 201), code


def main() -> None:
    call(TK, TK_KEY, "POST", "/__reset__")
    suffix = uuid.uuid4().hex[:8]

    happy = Saga("SAGA-OK-" + suffix)
    fund(happy, 500)
    start = happy.balance()
    happy.step_reserve()
    happy.step_payment(100)
    happy.step_delivery()
    assert happy.order_status() == "reserved" and happy.balance() == start - 100
    print("[ok] сага целиком: резерв стоит, баллы списаны, заявка создана")

    poor = Saga("SAGA-PAY-" + suffix)
    poor_start = poor.balance()
    poor.step_reserve()
    try:
        poor.step_payment(poor_start + 100)
        raise AssertionError("оплата сверх баланса прошла")
    except RuntimeError:
        assert poor.compensate()
    assert poor.order_status() == "cancelled" and poor.balance() == poor_start
    print("[ok] сбой оплаты (422 сверх баланса): резерв снят компенсацией, "
          "баллы не тронуты")

    broken = Saga("SAGA-SHIP-" + suffix)
    fund(broken, 500)
    broken_start = broken.balance()
    broken.step_reserve()
    broken.step_payment(100)
    try:
        broken.step_delivery(fault="error500")
        raise AssertionError("доставка при fault прошла")
    except RuntimeError:
        assert broken.compensate()
    compensations = [line for line in broken.journal if line.startswith("компенсация")]
    assert compensations == ["компенсация payment выполнена",
                             "компенсация reserve выполнена"], compensations
    assert broken.order_status() == "cancelled" and broken.balance() == broken_start
    print(f"[ok] сбой доставки: компенсации в обратном порядке {compensations}, "
          f"баллы возвращены сторно, а не удалением")

    code, _ = call(LOYALTY, LOYALTY_KEY, "POST",
                   f"/api/v1/reverse?operation_id={broken.id}-pay")
    assert code in (200, 409) and broken.balance() == broken_start
    print(f"[ok] двойная компенсация оплаты: ответ {code}, баланс не начислен второй раз")

    stuck = Saga("SAGA-STUCK-" + suffix)
    fund(stuck, 500)
    stuck_start = stuck.balance()
    stuck.step_reserve()
    stuck.step_payment(100)
    try:
        stuck.step_delivery(fault="error500")
    except RuntimeError:
        assert not stuck.compensate(fail_payment_compensation=True)
    assert stuck.manual_queue and stuck.manual_queue[0]["step"] == "payment"
    alerts = [line for line in stuck.journal if line.startswith("АЛЕРТ")]
    assert alerts
    print(f"[ok] неудавшаяся компенсация: {stuck.manual_queue[0]}; алерт записан сразу")
    assert stuck.compensate()
    assert stuck.balance() == stuck_start and stuck.order_status() == "cancelled"
    print("[ok] ручной повтор компенсации после снятия сбоя: данные сведены, "
          "сага закрыта честно")


if __name__ == "__main__":
    main()
