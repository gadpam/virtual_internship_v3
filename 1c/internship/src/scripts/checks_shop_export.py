#!/usr/bin/env python3
"""Проверки task_91: выгрузка в магазин — пакеты, дельта, частичный успех.

Гоняется против ОТДЕЛЬНОГО экземпляра mock_shop_api (свой порт, не
инфраструктурный :8020 и не :8026): полная выгрузка 100 000 позиций
пакетами по 500, дельта только изменённых, поименный rejected.

Запуск: SHOP_EXPORT_URL=http://127.0.0.1:8031 \
  src/scripts/.venv/bin/python src/scripts/checks_shop_export.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.request

BASE = os.environ.get("SHOP_EXPORT_URL", "http://127.0.0.1:8031")
KEY = os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key")
BATCH = 500


def put_products(items: list[dict]) -> dict:
    req = urllib.request.Request(BASE + "/api/v1/products", method="PUT")
    req.add_header("Content-Type", "application/json")
    req.add_header("X-Api-Key", KEY)
    req.data = json.dumps(items).encode()
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def export(items: list[dict]) -> tuple[int, int, float]:
    accepted = rejected = 0
    start = time.perf_counter()
    for i in range(0, len(items), BATCH):
        result = put_products(items[i:i + BATCH])
        accepted += result["accepted"]
        rejected += len(result["rejected"])
    return accepted, rejected, time.perf_counter() - start


def product(i: int, changed: str, price: float | None = None) -> dict:
    return {
        "external_id": f"EXT-{i:05d}", "sku": f"SKU-{i:05d}",
        "name": f"Товар {i}", "group": "Бакалея",
        "price": (10 + i % 97) if price is None else price,
        "currency": "BYN", "changed_at": changed,
    }


def main() -> None:
    base_changed = "2026-11-01T00:00:00Z"
    items = [product(i, base_changed) for i in range(100_000)]
    accepted, rejected, seconds = export(items)
    assert (accepted, rejected) == (100_000, 0), (accepted, rejected)
    print(f"[ok] полная выгрузка: 100000 принято за {seconds:.1f} с, пакетов {100_000 // BATCH}")

    watermark = base_changed
    changed = [product(i, "2026-11-17T00:00:00Z", price=999.0) for i in range(0, 100_000, 100)]
    delta = [p for p in changed if p["changed_at"] > watermark]
    accepted, rejected, seconds = export(delta)
    assert (accepted, rejected) == (len(delta), 0)
    print(f"[ok] дельта: изменено {len(delta)} из 100000, отправлено за {seconds:.2f} с")

    accepted, rejected, _ = export([])
    assert accepted == 0
    print("[ok] повторная дельта без изменений: отправлено 0")

    probe = [product(200001, base_changed), product(200002, base_changed, price=-5),
             product(200003, base_changed)]
    result = put_products(probe)
    assert result["accepted"] == 2 and len(result["rejected"]) == 1, result
    assert result["rejected"][0]["sku"] == "SKU-200002"
    print(f"[ok] частичный успех: принято 2, отклонён поименно {result['rejected'][0]['sku']}")


if __name__ == "__main__":
    main()
