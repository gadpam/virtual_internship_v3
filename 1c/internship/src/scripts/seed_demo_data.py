#!/usr/bin/env python3
"""Наполняет mock-сервисы учебными данными (task_73, task_91, task_141).

Заполняет онлайн-магазин, лояльность и трекер задачами так, чтобы стенд можно было
использовать в демонстрациях и тестах без ручного ввода.

Пример:
    python3 seed_demo_data.py --products 200 --orders 30 --dry-run
"""
import argparse
import asyncio
import json
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List

try:
    import httpx
except ImportError:  # pragma: no cover
    print("Нужен httpx: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)

DEFAULT_BASES = {
    "shop": "http://localhost:8020",
    "loyalty": "http://localhost:8021",
    "tracker": "http://localhost:8024",
}
API_KEYS = {"shop": "mock-shop-key", "loyalty": "mock-loyalty-key", "tracker": "mock-tracker-key"}

CATEGORIES = ["Бакалея", "Молочное", "Напитки", "Бытовая химия", "Свежие овощи"]
CITIES = ["Минск", "Брест", "Гродно", "Витебск", "Могилёв", "Гомель"]
TITLES = [
    "Ошибка выгрузки остатков в магазин",
    "Расхождение сумм в сверке RIH — БП",
    "Заказ не создан: дубль externalId",
    "ТК вернула 429 при массовой выгрузке",
    "Лояльность: баллы начислены дважды",
]


def make_products(count: int) -> List[Dict[str, object]]:
    now = datetime.now(timezone.utc)
    products = []
    for index in range(count):
        products.append({
            "external_id": f"ext-{index:05d}",
            "sku": f"SKU-{index:05d}",
            "name": f"Товар учебный {index} ({random.choice(CATEGORIES)})",
            "group": random.choice(CATEGORIES),
            "price": round(random.uniform(1.5, 900.0), 2),
            "currency": "BYN",
            "changed_at": (now - timedelta(hours=random.randint(0, 720))).isoformat(),
        })
    return products


def make_orders(count: int) -> List[Dict[str, object]]:
    orders = []
    for index in range(count):
        lines = [{"sku": f"SKU-{random.randint(0, 199):05d}",
                  "quantity": random.randint(1, 6),
                  "price": round(random.uniform(2.0, 200.0), 2)}
                 for _ in range(random.randint(1, 5))]
        orders.append({
            "external_id": f"SHOP-{index:06d}",
            "customer_ref": f"cust-{random.randint(1000, 9999)}",
            "lines": lines,
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=random.randint(1, 4320))).isoformat(),
        })
    return orders


async def seed(base_urls: Dict[str, str], products: int, orders: int, issues: int,
               dry_run: bool) -> Dict[str, object]:
    plan = {"products": products, "orders": orders, "issues": issues, "dryRun": dry_run}
    if dry_run:
        print(json.dumps({"plan": plan, "note": "dry-run: запросы не отправлялись"}, ensure_ascii=False, indent=2))
        return plan

    result: Dict[str, object] = {}
    async with httpx.AsyncClient(timeout=15) as client:
        payload = make_products(products)
        response = await client.put(f"{base_urls['shop']}/api/v1/products",
                                    json=payload,
                                    headers={"X-Api-Key": API_KEYS["shop"]})
        result["shop_products"] = {"status": response.status_code, "body": response.json()}

        created = 0
        for order in make_orders(orders):
            response = await client.post(f"{base_urls['shop']}/api/v1/orders",
                                         json=order,
                                         headers={"X-Api-Key": API_KEYS["shop"],
                                                  "Idempotency-Key": str(uuid.uuid4())})
            if response.status_code == 201:
                created += 1
        result["shop_orders_created"] = created

        for index in range(issues):
            response = await client.post(f"{base_urls['tracker']}/api/v1/issues",
                                         json={"external_ref": f"РИХ_Инцидент/{uuid.uuid4()}",
                                               "title": TITLES[index % len(TITLES)],
                                               "description": f"Учебный инцидент №{index + 1}, город {random.choice(CITIES)}",
                                               "priority": random.choice(["low", "medium", "high", "critical"]),
                                               "due_in_hours": random.choice([4, 8, 24, 72])},
                                         headers={"X-Api-Key": API_KEYS["tracker"]})
            if response.status_code not in (200, 201):
                print(f"трекер: {response.status_code} {response.text[:100]}", file=sys.stderr)
        result["tracker_issues"] = issues

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Наполнение mock-сервисов учебными данными")
    parser.add_argument("--shop", default=DEFAULT_BASES["shop"])
    parser.add_argument("--loyalty", default=DEFAULT_BASES["loyalty"])
    parser.add_argument("--tracker", default=DEFAULT_BASES["tracker"])
    parser.add_argument("--products", type=int, default=200)
    parser.add_argument("--orders", type=int, default=30)
    parser.add_argument("--issues", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true", help="показать план, ничего не отправляя")
    args = parser.parse_args()

    base_urls = {"shop": args.shop.rstrip("/"), "loyalty": args.loyalty.rstrip("/"),
                 "tracker": args.tracker.rstrip("/")}
    asyncio.run(seed(base_urls, args.products, args.orders, args.issues, args.dry_run))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
