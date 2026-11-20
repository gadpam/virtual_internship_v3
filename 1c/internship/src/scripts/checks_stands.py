#!/usr/bin/env python3
"""Проверки task_139: детерминированность данных и подъём стенда.

Два поколения фикстур байт-в-байт совпадают; состав — по заданию
(500 товаров, 20 складов, 100 заказов, прайс, остатки); стенд
поднимается одной командой дважды с одинаковой контрольной суммой;
профили объёма переключаются параметром.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_stands.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seed_fixtures import generate, render  # noqa: E402
from stand_up import psql  # noqa: E402


def main() -> None:
    first, second = render(generate("small")), render(generate("small"))
    assert first == second
    data = generate("small")
    assert len(data["products"]) == 500
    assert len(data["warehouses"]) == 20
    assert len(data["orders"]) == 100
    assert all(row["price"] > 0 for row in data["products"])
    assert len(data["stock"]) == 500
    assert data["orders"][0]["external_id"] == "ORD-0001"
    print("[ok] детерминированность: два поколения байт-в-байт, состав по заданию")

    assert len(generate("medium")["orders"]) == 2_000
    assert len(generate("large")["products"]) == 50_000
    print("[ok] профили объёма: small/medium/large одним параметром")

    sums = []
    for run in (1, 2):
        started = time.time()
        proc = subprocess.run(
            [sys.executable, "src/scripts/stand_up.py", "small"],
            capture_output=True, text=True, timeout=300)
        assert proc.returncode == 0, proc.stderr
        sums.append(psql("SELECT round(sum(total), 2) FROM stand.orders"))
        print(f"[ok] подъём стенда №{run} одной командой: {time.time() - started:.1f} с")
    assert sums[0] == sums[1] and sums[0] not in ("", "0")
    print(f"[ok] два подъёма — одна контрольная сумма заказов: {sums[0]}")


if __name__ == "__main__":
    main()
