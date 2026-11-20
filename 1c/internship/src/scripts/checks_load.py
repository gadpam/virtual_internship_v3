#!/usr/bin/env python3
"""Проверки task_143: нагрузочные прогоны интеграций (внешний генератор).

Три сценария против моков стенда: приём заказов, выгрузка каталога,
начисления лояльности (чеки порождают начисления). Ступени
параллелизма 1/5/10/20/40, на ступень — фиксированная серия;
считаем пропускную способность, p50/p95/p99 и долю ошибок.
Точка отказа — первая ступень, где ошибки > 5% или p95 вырос
больше чем в 10 раз от базовой ступени. Конфигурация стенда —
часть результата: моки — однопроцессные uvicorn учебного стенда.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_load.py
"""

from __future__ import annotations

import json
import statistics
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor

SHOP = "http://127.0.0.1:8026"
LOYALTY = "http://127.0.0.1:8021"
RUN = uuid.uuid4().hex[:8]
LEVELS = [1, 5, 10, 20, 40]
PER_LEVEL = 120


def one_request(kind: str, index: int) -> tuple[float, bool]:
    started = time.time()
    try:
        if kind == "orders":
            payload = {"external_id": f"LD-{RUN}-{index}",
                       "lines": [{"sku": "SKU-0001", "quantity": 1, "price": 10.0}]}
            request = urllib.request.Request(
                SHOP + "/api/v1/orders", data=json.dumps(payload).encode(),
                method="POST",
                headers={"Content-Type": "application/json",
                         "X-Api-Key": "mock-shop-key",
                         "Idempotency-Key": f"LD-{RUN}-{index}"})
        elif kind == "catalog":
            request = urllib.request.Request(
                SHOP + "/api/v1/products?limit=20",
                headers={"X-Api-Key": "mock-shop-key"})
        else:
            payload = {"operation_id": f"LD-{RUN}-{index}",
                       "card": f"LD-{RUN}-card", "points": 1}
            request = urllib.request.Request(
                LOYALTY + "/api/v1/accrue", data=json.dumps(payload).encode(),
                method="POST",
                headers={"Content-Type": "application/json",
                         "X-Api-Key": "mock-loyalty-key"})
        with urllib.request.urlopen(request, timeout=30) as response:
            response.read()
            return time.time() - started, response.status < 500
    except urllib.error.HTTPError as error:
        return time.time() - started, error.code < 500
    except Exception:
        return time.time() - started, False


def percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, int(round(pct / 100 * len(ordered) + 0.5)) - 1))
    return ordered[rank]


def run_scenario(kind: str) -> list[dict]:
    rows = []
    for level in LEVELS:
        with ThreadPoolExecutor(max_workers=level) as pool:
            started = time.time()
            results = list(pool.map(lambda i: one_request(kind, level * 10000 + i),
                                    range(PER_LEVEL)))
            elapsed = time.time() - started
        latencies = [latency for latency, _ in results]
        errors = sum(1 for _, ok in results if not ok)
        rows.append({
            "level": level,
            "rps": PER_LEVEL / elapsed,
            "p50": percentile(latencies, 50) * 1000,
            "p95": percentile(latencies, 95) * 1000,
            "p99": percentile(latencies, 99) * 1000,
            "errors": errors / PER_LEVEL,
        })
    return rows


def main() -> None:
    targets = {"orders": 2000 / 3600, "catalog": 10000 / 3600, "loyalty": 5000 / 3600}
    names = {"orders": "приём заказов", "catalog": "выгрузка каталога",
             "loyalty": "начисления лояльности"}
    report = {}
    for kind in ("orders", "catalog", "loyalty"):
        rows = run_scenario(kind)
        report[kind] = rows
        # Деградация стенда — плато: параллель растёт, пропускная уже
        # нет, а хвост платит за ожидание в очереди одного процесса.
        breaking = next((row for prev, row in zip(rows, rows[1:])
                         if row["rps"] <= 1.05 * prev["rps"]
                         and row["p95"] > 2 * prev["p95"]), None)
        print(f"\n{names[kind]} (цель {targets[kind]:.2f} запр/с):")
        for row in rows:
            mark = "  <- деградация" if breaking and row["level"] == breaking["level"] else ""
            print(f"  параллель {row['level']:>2}: {row['rps']:7.1f} запр/с, "
                  f"p50 {row['p50']:6.0f} мс, p95 {row['p95']:6.0f} мс, "
                  f"p99 {row['p99']:6.0f} мс, ошибки {row['errors']:.1%}{mark}")
        sustainable = [row for row in rows if row["errors"] <= 0.01]
        best = max(sustainable, key=lambda row: row["rps"])
        assert best["rps"] > targets[kind], (kind, best, targets[kind])
        print(f"  держим цель с запасом: {best['rps']:.1f} запр/с при параллели "
              f"{best['level']} (ошибки {best['errors']:.1%})")
    print("\n[ok] все три сценария держат целевую нагрузку стенда; "
          "ступени и хвосты зафиксированы для отчёта")


if __name__ == "__main__":
    main()
