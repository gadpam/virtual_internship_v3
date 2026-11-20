#!/usr/bin/env python3
"""Canary-проверка партнёра (task_140): лёгкий запрос по расписанию.

Смысл: партнёр поменял формат во вторник — мы узнали во вторник
от canary, а не в ночь обмена от бизнеса. Проверка валидирует
живой ответ против OpenAPI-схемы; при расхождении — код выхода 1
и строка ALERT для мониторинга (canary без алерта бесполезна:
проверка есть, а узнаёт о ней всё равно бизнес).

Запуск: src/scripts/.venv/bin/python src/scripts/canary_check.py [base_url]
"""

from __future__ import annotations

import json
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from checks_contracts import errors, load_schemas  # noqa: E402


def main(argv: list[str]) -> int:
    base = argv[0] if argv else "http://127.0.0.1:8026"
    schemas = load_schemas()
    try:
        with urllib.request.urlopen(base + "/health", timeout=5) as response:
            health = json.loads(response.read())
        problems = errors(schemas["Health"], health)
        if problems:
            print(f"ALERT canary {base}: /health не по контракту: "
                  f"{[p.message for p in problems]}")
            return 1
        request = urllib.request.Request(
            base + "/api/v1/products?limit=2",
            headers={"X-Api-Key": "mock-shop-key"})
        with urllib.request.urlopen(request, timeout=5) as response:
            page = json.loads(response.read())
        problems = errors(schemas["ProductList"], page)
        for item in page.get("items", []):
            problems += errors(schemas["Product"], item)
        if problems:
            print(f"ALERT canary {base}: каталог не по контракту: "
                  f"{[p.message for p in problems]}")
            return 1
    except Exception as exc:  # недоступность партнёра — тоже сигнал canary
        print(f"ALERT canary {base}: партнёр недоступен: {exc}")
        return 1
    print(f"canary {base}: контракт жив (health, каталог)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
