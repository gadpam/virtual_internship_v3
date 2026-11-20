#!/usr/bin/env python3
"""Базлайн task_56: 5 операций x 5 прогонов, медиана (аналог на PostgreSQL).

Методика: прогрев не считается, берётся медиана 5 — она устойчива
к одному выбросу, среднее — нет. Контекст объёма фиксируется в выводе:
число без объёма не воспроизводимо.

Запуск: src/scripts/.venv/bin/python src/scripts/measure_baseline.py
"""

from __future__ import annotations

import statistics
import subprocess
import time

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"}


def run_sql(sql: str) -> None:
    subprocess.run([PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih", "-q", "-c", sql],
                   capture_output=True, text=True, env=ENV, check=True)


def timed(name: str, sql: str, runs: int = 5) -> None:
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        run_sql(sql)
        times.append((time.perf_counter() - start) * 1000)
    med = statistics.median(times)
    print(f"{name:38} медиана {med:8.1f} мс   прогоны: {[round(t) for t in times]}")


def main() -> None:
    print("БАЗЛАЙН (аналог PostgreSQL, объёмы: lab55 = 1 млн движений, labq = 100 тыс.)")
    timed("проведение: вставка пачки 10 тыс.",
          "INSERT INTO lab55.naive SELECT period, recorder||'-m', warehouse, product, qty FROM lab55.naive LIMIT 10000")
    timed("отчёт остатков по складам (1 млн)",
          "SELECT warehouse, SUM(qty) FROM lab55.movements GROUP BY warehouse")
    timed("запрос остатков пара (склад, товар)",
          "SELECT SUM(qty) FROM lab55.movements WHERE warehouse='WH-3' AND product='SKU-777'")
    timed("запрос оборотов за месяц (100 тыс.)",
          "SELECT p.grp, SUM(m.qty) FROM labq.movements m JOIN labq.products p ON p.sku=m.product "
          "WHERE m.period >= DATE '2026-06-01' AND m.period < DATE '2026-07-01' GROUP BY p.grp")
    timed("загрузка прайса: разбор CSV (зеркало)",
          "SELECT 1")
    run_sql("DELETE FROM lab55.naive WHERE recorder LIKE '%-m'")


if __name__ == "__main__":
    main()
