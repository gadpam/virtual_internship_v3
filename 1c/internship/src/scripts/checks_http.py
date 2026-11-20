#!/usr/bin/env python3
"""Проверки task_74: семантика HTTP на живом mock_shop_api (:8020).

Статусы: 200/201/401/403/404/409/422 и идемпотентность POST /orders:
тот же external_id + Idempotency-Key = тот же результат, без ключа
или с чужим ключом = 409, а не второй заказ.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_http.py
Требуется поднятый mock (стенд task_72); ключ — учебный, из окружения.
"""

from __future__ import annotations

import json
import os
import urllib.request
import urllib.error
import uuid

BASE = os.getenv("MOCK_SHOP_URL", "http://127.0.0.1:8020")
KEY = os.getenv("MOCK_SHOP_API_KEY", "mock-shop-key")


def call(method: str, path: str, body: dict | None = None,
         key: str | None = KEY, extra: dict | None = None) -> tuple[int, dict]:
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


def expect(name: str, got: int, want: int) -> None:
    assert got == want, f"{name}: ожидался {want}, получен {got}"
    print(f"[ok] {name}: {got}")


def main() -> None:
    status, body = call("GET", "/health", key=None)
    expect("GET /health без ключа (публичный)", status, 200)
    assert body["status"] == "ok"

    status, _ = call("GET", "/api/v1/products", key=None)
    expect("GET /products без ключа", status, 401)
    status, _ = call("GET", "/api/v1/products", key="wrong-key")
    expect("GET /products с неверным ключом", status, 403)
    status, body = call("GET", "/api/v1/products")
    expect("GET /products с ключом", status, 200)
    assert body["total"] >= 50

    ext = f"demo-{uuid.uuid4().hex[:8]}"
    order = {"external_id": ext, "lines": [{"sku": "SKU-00001", "quantity": 2, "price": 10.5}]}
    status, body = call("POST", "/api/v1/orders", order, extra={"Idempotency-Key": "k-1"})
    expect("POST /orders создание", status, 201)
    assert body["total"] == 21.0 and body["duplicate"] is False

    status, body = call("POST", "/api/v1/orders", order, extra={"Idempotency-Key": "k-1"})
    expect("POST /orders повтор тем же ключом", status, 201)
    assert body["duplicate"] is True, body
    print("[ok] повтор не создал дубль: duplicate=true, итог тот же")

    status, _ = call("POST", "/api/v1/orders", order, extra={"Idempotency-Key": "k-2"})
    expect("POST /orders тот же заказ, другой ключ", status, 409)

    status, _ = call("POST", "/api/v1/orders", {"external_id": "x"})  # нет lines
    expect("POST /orders мусор (нет строк)", status, 422)

    status, _ = call("PATCH", "/api/v1/orders/no-such/status?status=shipped")
    expect("PATCH статуса несуществующего заказа", status, 404)

    status, body = call("PATCH", f"/api/v1/orders/{ext}/status?status=shipped")
    expect("PATCH статуса существующего", status, 200)
    assert body["status"] == "shipped"


if __name__ == "__main__":
    main()
