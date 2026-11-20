#!/usr/bin/env python3
"""Контрактные тесты task_96: фикстуры против живых реализаций mock.

Контракт — это фикстуры и OpenAPI, а не «как сейчас отвечает сервер»:
валидные заказы обязаны приниматься, бракованные — отклоняться
с записанным кодом, операции лояльности — быть идемпотентными,
каталог — совпадать по составу полей с эталонной фикстурой.
Падение здесь = контракт изменён молча.

Запуск (свой магазин :8031 и обновлённый :8026, лояльность :8021):
  src/scripts/.venv/bin/python src/scripts/checks_contract.py
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

FIXTURES = Path("tests/fixtures")
SHOP_NEW = os.environ.get("SHOP_EXPORT_URL", "http://127.0.0.1:8031")
SHOP = os.environ.get("MOCK_SHOP_URL", "http://127.0.0.1:8026")
LOYALTY = "http://127.0.0.1:8021"
KEYS = {"shop": os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key"),
        "loyalty": "mock-loyalty-key"}


def call(base: str, key: str, method: str, path: str,
         body: dict | None = None, extra: dict | None = None) -> tuple[int, dict]:
    req = urllib.request.Request(base + path, method=method)
    req.add_header("X-Api-Key", key)
    for name, value in (extra or {}).items():
        req.add_header(name, value)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode() or "{}")


def main() -> None:
    fixture = json.loads((FIXTURES / "shop_products.json").read_text(encoding="utf-8"))
    status, live = call(SHOP, KEYS["shop"], "GET", "/api/v1/products?limit=50")
    assert status == 200 and live["total"] == fixture["total"], (status, live.get("total"))
    assert set(live["items"][0]) == set(fixture["items"][0]), "состав полей каталога разошёлся с фикстурой"
    print(f"[ok] каталог: total {live['total']}, поля совпадают с фикстурой")

    valid = json.loads((FIXTURES / "orders_valid.json").read_text(encoding="utf-8"))["cases"]
    for case in valid:
        body = {"external_id": "CT96-" + uuid.uuid4().hex[:8],
                "customer_ref": case["customer_ref"], "lines": case["lines"],
                "created_at": "2026-11-17T10:00:00Z"}
        status, _ = call(SHOP_NEW, KEYS["shop"], "POST", "/api/v1/orders", body,
                         {"Idempotency-Key": str(uuid.uuid4())})
        assert status == 201, (case["name"], status)
    print(f"[ok] валидных заказов принято: {len(valid)} из {len(valid)}")

    invalid = json.loads((FIXTURES / "orders_invalid.json").read_text(encoding="utf-8"))["cases"]
    for case in invalid:
        body = dict(case["payload"])
        if "external_id" in body:
            # Уникализируем только существующий id: случай «нет external_id»
            # обязан остаться без него, иначе тест починит брак за сервис.
            body["external_id"] = str(body["external_id"]) + "-" + uuid.uuid4().hex[:6]
        status, _ = call(SHOP_NEW, KEYS["shop"], "POST", "/api/v1/orders", body,
                         {"Idempotency-Key": str(uuid.uuid4())})
        assert status == case["expected_status"], (case["name"], status, case["expected_status"])
    print(f"[ok] бракованных отклонено с ожидаемыми кодами: {len(invalid)} из {len(invalid)}")

    loyalty = json.loads((FIXTURES / "loyalty_operations.json").read_text(encoding="utf-8"))
    accrue = dict(loyalty["accrue"])
    accrue["operation_id"] = "CT96-" + uuid.uuid4().hex[:8]
    _, first = call(LOYALTY, KEYS["loyalty"], "POST", "/api/v1/accrue", accrue)
    _, second = call(LOYALTY, KEYS["loyalty"], "POST", "/api/v1/accrue", accrue)
    assert second["duplicate"] is True
    _, balance = call(LOYALTY, KEYS["loyalty"], "GET", f"/api/v1/cards/{accrue['card']}/balance")
    assert balance["balance"] == first["balance"]
    print("[ok] лояльность по фикстуре: начисление идемпотентно, баланс не двоится")

    ET.fromstring((FIXTURES / "soap_bank.xml").read_text(encoding="utf-8"))
    print("[ok] SOAP-фикстура банка — корректный XML")


if __name__ == "__main__":
    main()
