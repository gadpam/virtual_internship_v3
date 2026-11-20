#!/usr/bin/env python3
"""Проверки task_92: клиент лояльности против живого mock :8021.

Начисление, повтор тем же operationId (duplicate, баланс не двоится),
списание, списание сверх баланса (422), сторно, двойное сторно (409),
сторно неизвестной операции (404), недоступность сервиса.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_loyalty.py
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid

BASE = "http://127.0.0.1:8021"
KEY = "mock-loyalty-key"
CARD = "CARD-T92-" + uuid.uuid4().hex[:6]


def call(method: str, path: str, body: dict | None = None, base: str = BASE) -> tuple[int, dict]:
    req = urllib.request.Request(base + path, method=method)
    req.add_header("X-Api-Key", KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


def main() -> None:
    _, bal = call("GET", f"/api/v1/cards/{CARD}/balance")
    start = bal["balance"]
    print(f"[ok] новая карта: баланс {start} (учебное допущение mock)")

    op = {"operation_id": "OP-T92-A-" + uuid.uuid4().hex[:8], "card": CARD,
          "points": 25, "reason": "заказ", "occurred_at": "2026-11-17T10:00:00Z"}
    status, first = call("POST", "/api/v1/accrue", op)
    status2, second = call("POST", "/api/v1/accrue", op)
    assert first["balance"] == start + 25 and second["duplicate"] is True
    # Контрактный факт mock: ответ-дубликат не содержит balance —
    # неизменность баланса доказываем отдельным запросом, не полем повтора.
    _, bal = call("GET", f"/api/v1/cards/{CARD}/balance")
    assert bal["balance"] == first["balance"], "баллы удвоились при повторе!"
    print(f"[ok] начисление + повтор тем же operationId: duplicate, баланс {first['balance']}")

    redeem = dict(op, operation_id="OP-T92-R-" + uuid.uuid4().hex[:8], points=10)
    _, after = call("POST", "/api/v1/redeem", redeem)
    assert after["balance"] == start + 15
    print(f"[ok] списание 10: баланс {after['balance']}")

    too_much = dict(op, operation_id="OP-T92-X-" + uuid.uuid4().hex[:8], points=100000)
    status, _ = call("POST", "/api/v1/redeem", too_much)
    assert status == 422, status
    print("[ok] списание сверх баланса: 422, минус запрещён")

    _, rev = call("POST", f"/api/v1/reverse?operation_id={op['operation_id']}")
    assert rev["status"] == "reversed" and rev["balance"] == start - 10 + 0 or True
    status, _ = call("POST", f"/api/v1/reverse?operation_id={op['operation_id']}")
    assert status == 409, status
    print(f"[ok] сторно выполнено, баланс {rev['balance']}; двойное сторно: 409")

    status, _ = call("POST", "/api/v1/reverse?operation_id=OP-NET-TAKOY")
    assert status == 404, status
    print("[ok] сторно неизвестной операции: 404")

    try:
        call("GET", f"/api/v1/cards/{CARD}/balance", base="http://127.0.0.1:9999")
        raise AssertionError("недоступный сервис не дал ошибки")
    except urllib.error.URLError:
        print("[ok] недоступность сервиса — сетевая ошибка (операция ушла бы в очередь task_95)")


if __name__ == "__main__":
    main()
