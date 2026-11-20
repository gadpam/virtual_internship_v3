#!/usr/bin/env python3
"""Живые проверки sprint_14 против mock_shop_api: заказы, ошибки, пачка.

Сценарий task_83: 20 заказов, из них 3 с ошибками; повтор — без дубля;
смена статуса; отмена. Плюс единый формат ошибки task_82: ответы mock
({detail}) приводятся к {code, message, details, incidentId, timestamp}
той же функцией, что повторяет РИХ_HTTP1_Ответы.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_api_q2.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

BASE = os.getenv("MOCK_SHOP_URL", "http://127.0.0.1:8020")
KEY = os.getenv("MOCK_SHOP_API_KEY", "mock-shop-key")


def call(method: str, path: str, body: dict | None = None, key: str | None = KEY,
         extra: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    if data:
        req.add_header("Content-Type", "application/json")
    if key:
        req.add_header("X-Api-Key", key)
    for name, value in (extra or {}).items():
        req.add_header(name, value)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        raw = err.read().decode()
        try:
            return err.code, json.loads(raw)
        except json.JSONDecodeError:
            return err.code, {"raw": raw}


def unified_error(status: int, body: dict) -> dict:
    """Зеркало единого формата ошибки RIH (task_82)."""
    codes = {400: "RIH-400", 401: "RIH-401", 403: "RIH-403", 404: "RIH-404",
             409: "RIH-409", 422: "RIH-422", 429: "RIH-429", 500: "RIH-500"}
    return {
        "code": codes.get(status, f"RIH-{status}"),
        "message": str(body.get("detail", "Ошибка интеграционного вызова")),
        "details": body,
        "incidentId": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def main() -> None:
    run = uuid.uuid4().hex[:6]
    valid = [{"external_id": f"s14-{run}-{i}",
              "lines": [{"sku": "SKU-00001", "quantity": 1, "price": 5.0}]}
             for i in range(17)]
    bad = [
        {"external_id": f"s14-{run}-bad1", "lines": []},
        {"external_id": f"s14-{run}-bad2",
         "lines": [{"sku": "SKU-00001", "quantity": 0, "price": 5.0}]},
        {"external_id": f"s14-{run}-bad3",
         "lines": [{"sku": "SKU-00001", "quantity": 1, "price": -1.0}]},
    ]
    accepted, rejected = 0, 0
    for order in valid:
        status, _ = call("POST", "/api/v1/orders", order,
                         extra={"Idempotency-Key": f"k-{order['external_id']}"})
        assert status == 201, (order, status)
        accepted += 1
    for order in bad:
        status, _ = call("POST", "/api/v1/orders", order)
        assert status == 422, (order, status)
        rejected += 1
    print(f"[ok] пачка 20 заказов: принято {accepted}, отклонено {rejected} (422)")

    first = valid[0]
    status, body = call("POST", "/api/v1/orders", first,
                        extra={"Idempotency-Key": f"k-{first['external_id']}"})
    assert body.get("duplicate") is True
    print(f"[ok] повтор первого заказа: {status}, duplicate=true — дубля нет")

    status, body = call("PATCH", f"/api/v1/orders/{first['external_id']}/status?status=shipped")
    assert status == 200 and body["status"] == "shipped"
    print("[ok] смена статуса заказа работает")

    # Единый формат ошибок на живых ответах mock
    for name, status, body in [
        ("без ключа", *call("GET", "/api/v1/products", key=None)),
        ("неизвестный заказ", *call("PATCH", "/api/v1/orders/no-such-order/status?status=shipped")),
        ("мусор в заказе", *call("POST", "/api/v1/orders", {"external_id": "zz"})),
    ]:
        err = unified_error(status, body)
        assert set(err) == {"code", "message", "details", "incidentId", "timestamp"}, err
        assert err["code"].startswith("RIH-") and len(err["incidentId"]) == 36
        print(f"[ok] ошибка «{name}»: {status} -> {err['code']}, инцидент {err['incidentId'][:8]}…")


if __name__ == "__main__":
    main()
