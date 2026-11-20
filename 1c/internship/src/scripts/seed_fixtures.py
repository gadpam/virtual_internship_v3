#!/usr/bin/env python3
"""Генератор эталонных данных стенда (task_139).

Детерминированность — формулами от индекса, а не генератором
случайных чисел: два прогона в любой день дают байт-в-байт один
файл. Даты фиксированы (2026-01-01..), идентификаторы — SKU-0001,
WH-01, ORD-0001: тесты ищут объекты по id и не падают от «сегодня».

Объёмы одним параметром профиля: small (тесты), medium (отладка),
large (нагрузка task_143) — не тремя скриптами.

Использование:
    seed_fixtures.py [small|medium|large] [путь-результата]
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

PROFILES = {
    "small": {"products": 500, "warehouses": 20, "orders": 100},
    "medium": {"products": 5_000, "warehouses": 20, "orders": 2_000},
    "large": {"products": 50_000, "warehouses": 40, "orders": 100_000},
}
BASE_DATE = "2026-01-15"  # фиксированная дата стенда, не «сегодня»


def generate(profile: str) -> dict:
    size = PROFILES[profile]
    products = [
        {"sku": f"SKU-{i:04d}", "name": f"Товар стенда {i:04d}",
         "price": round(10 + (i * 37 % 990) + 0.99, 2)}
        for i in range(1, size["products"] + 1)
    ]
    warehouses = [
        {"code": f"WH-{i:02d}", "name": f"Склад стенда {i:02d}",
         "city": ["Минск", "Гомель", "Витебск", "Гродно"][i % 4]}
        for i in range(1, size["warehouses"] + 1)
    ]
    stock = [
        {"sku": product["sku"], "warehouse": warehouses[i % len(warehouses)]["code"],
         "quantity": (i * 13) % 200}
        for i, product in enumerate(products)
    ]
    orders = []
    for i in range(1, size["orders"] + 1):
        lines = [
            {"sku": f"SKU-{(i * 3 + j) % size['products'] + 1:04d}",
             "quantity": (i + j) % 5 + 1,
             "price": products[(i * 3 + j) % size["products"]]["price"]}
            for j in range(1, (i % 3) + 2)
        ]
        orders.append({"external_id": f"ORD-{i:04d}", "date": BASE_DATE,
                       "warehouse": warehouses[i % len(warehouses)]["code"],
                       "lines": lines,
                       "total": round(sum(l["quantity"] * l["price"] for l in lines), 2)})
    return {"profile": profile, "base_date": BASE_DATE,
            "products": products, "warehouses": warehouses,
            "stock": stock, "orders": orders}


def render(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      indent=1).encode("utf-8")


def main(argv: list[str]) -> int:
    profile = argv[0] if argv else "small"
    target = Path(argv[1]) if len(argv) > 1 else \
        Path("tests/fixtures/stand_data.json")
    blob = render(generate(profile))
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    print(f"профиль {profile}: {target} ({len(blob)} байт, sha256 {digest})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
