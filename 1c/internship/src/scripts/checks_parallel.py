#!/usr/bin/env python3
"""Проверки task_59: параллельный пересчёт шардами на аналоге PostgreSQL.

Шарды — склады lab55 (1 млн движений). Агрегат повторяется 10 раз внутри
одного сеанса psql: время старта процесса не должно съедать замер
(методика task_56). Параллелизм самой СУБД внутри запроса отключён
(max_parallel_workers_per_gather=0): шардинг — единственный источник
параллелизма, как в типовых запросах 1С. Итог параллельного прогона
обязан совпасть с последовательным.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_parallel.py
"""

from __future__ import annotations

import subprocess
import time
from concurrent.futures import ProcessPoolExecutor

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only",
       "PGOPTIONS": "-c max_parallel_workers_per_gather=0"}
WAREHOUSES = [f"WH-{i}" for i in range(10)]


def shard_sum(warehouses: list[str]) -> float:
    quoted = ",".join(f"'{w}'" for w in warehouses)
    sql = ("SELECT SUM(t) / 10 FROM (SELECT "
           f"(SELECT COALESCE(SUM(qty), 0) FROM lab55.movements "
           f"WHERE warehouse IN ({quoted})) AS t "
           "FROM generate_series(1, 10)) r")
    proc = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih",
         "-t", "-A", "-c", sql],
        capture_output=True, text=True, env=ENV)
    return float(proc.stdout.strip())


def split(items: list[str], parts: int) -> list[list[str]]:
    shards: list[list[str]] = [[] for _ in range(parts)]
    for i, item in enumerate(items):
        shards[i % parts].append(item)
    return [s for s in shards if s]


def run(workers: int) -> tuple[float, float]:
    shards = split(WAREHOUSES, workers)
    start = time.perf_counter()
    if workers == 1:
        total = sum(shard_sum(s) for s in shards)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            total = sum(pool.map(shard_sum, shards))
    return total, (time.perf_counter() - start) * 1000


def main() -> None:
    base, t1 = run(1)
    print(f"[ok] 1 поток:  {t1:8.1f} мс, итог {base}")
    for workers in (2, 4):
        total, ms = run(workers)
        assert total == base, (total, base)
        print(f"[ok] {workers} потока: {ms:8.1f} мс, итог совпал, ускорение x{t1 / ms:.2f}")


if __name__ == "__main__":
    main()
