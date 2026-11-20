#!/usr/bin/env python3
"""Проверки task_57: пакеты, возобновление после сбоя, выбор размера пакета.

Зеркало РИХ_ПакетнаяОбработка на PostgreSQL: транзакция на пакет,
искуственный сбой на пакете 3 из 5, возобновление с пакета 3.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_batches.py
"""

from __future__ import annotations

import subprocess
import time

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"}


def sql(query: str, tuples: bool = False) -> str:
    cmd = [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih", "-c", query]
    if tuples:
        cmd += ["-t", "-A"]
    proc = subprocess.run(cmd, capture_output=True, text=True, env=ENV)
    return proc.stdout.strip()


def load_batch(start_pkg: int, size: int, total_pkgs: int, fail_at: int = 0) -> int:
    """Возвращает номер последнего завершённого пакета; сбой бросает исключение."""
    done = start_pkg - 1
    for pkg in range(start_pkg, total_pkgs + 1):
        if pkg == fail_at:
            raise RuntimeError(f"искусственный сбой пакета {pkg} (пакет откачен)")
        sql(f"INSERT INTO lab57.out SELECT {(pkg - 1) * size} + g FROM generate_series(1, {size}) g")
        done = pkg
    return done


def main() -> None:
    sql("CREATE SCHEMA IF NOT EXISTS lab57; DROP TABLE IF EXISTS lab57.out; CREATE TABLE lab57.out (n int)")
    try:
        load_batch(1, 100, 5, fail_at=3)
        raise AssertionError("сбой не произошёл")
    except RuntimeError as err:
        print(f"[ok] сбой: {err}")
    rows_after_crash = int(sql("SELECT COUNT(*) FROM lab57.out", tuples=True))
    assert rows_after_crash == 200, rows_after_crash
    print(f"[ok] после сбоя зафиксировано ровно 2 пакета = {rows_after_crash} строк")
    last = load_batch(3, 100, 5)
    total = int(sql("SELECT COUNT(*) FROM lab57.out", tuples=True))
    distinct = int(sql("SELECT COUNT(DISTINCT n) FROM lab57.out", tuples=True))
    assert total == 500 and distinct == 500, (total, distinct)
    print(f"[ok] возобновление с пакета {last - 2}: итог {total} строк без дублей")

    for size in (100, 1000, 10000):
        sql("TRUNCATE lab57.out")
        start = time.perf_counter()
        pkgs = 100000 // size
        load_batch(1, size, pkgs)
        ms = (time.perf_counter() - start) * 1000
        print(f"[ok] 100 тыс. пакетом {size:6}: {ms:7.1f} мс ({pkgs} транзакций)")


if __name__ == "__main__":
    main()
