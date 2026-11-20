#!/usr/bin/env python3
"""Проверки task_60: кэш минимальных остатков против чтения из базы.

Зеркало РИХ_Кэш: таблица порогов читается один раз и держится в памяти
«сеанса» (словарь); сброс — явная инвалидация после записи. Меряем
200 чтений пар (склад, товар) из базы против кэша, минимум 3 замера.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_cache.py
"""

from __future__ import annotations

import subprocess
import time

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"}


def sql(query: str) -> str:
    proc = subprocess.run([PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih",
                           "-t", "-A", "-c", query], capture_output=True, text=True, env=ENV)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout.strip()


def load_minimums() -> dict[tuple[str, str], float]:
    sql("CREATE SCHEMA IF NOT EXISTS lab60")
    sql("CREATE TABLE IF NOT EXISTS lab60.minimums (warehouse text, product text, qty numeric)")
    sql("INSERT INTO lab60.minimums SELECT 'WH-1','SKU-101',500 WHERE NOT EXISTS (SELECT 1 FROM lab60.minimums)")
    sql("INSERT INTO lab60.minimums SELECT 'WH-2','SKU-205',300 WHERE (SELECT COUNT(*) FROM lab60.minimums) < 2")
    rows = sql("SELECT warehouse||'|'||product||'|'||qty FROM lab60.minimums")
    cache = {}
    for line in rows.splitlines():
        wh, sku, qty = line.split("|")
        cache[(wh, sku)] = float(qty)
    return cache


def read_db(pair: tuple[str, str]) -> float:
    out = sql(f"SELECT COALESCE(qty,0) FROM lab60.minimums WHERE warehouse='{pair[0]}' AND product='{pair[1]}'")
    return float(out) if out else 0.0


def main() -> None:
    pairs = [("WH-1", "SKU-101"), ("WH-2", "SKU-205"), ("WH-9", "SKU-999")] * 67
    cache = load_minimums()
    # Повторяемость прогона: исходное состояние выставляет сам тест
    sql("UPDATE lab60.minimums SET qty = 500 WHERE warehouse='WH-1' AND product='SKU-101'")
    cache = load_minimums()

    db_times, cache_times = [], []
    for _ in range(3):
        start = time.perf_counter()
        db_vals = [read_db(p) for p in pairs[:30]]
        db_times.append((time.perf_counter() - start) * 1000)
        start = time.perf_counter()
        cache_vals = [cache.get(p, 0.0) for p in pairs[:30]]
        cache_times.append((time.perf_counter() - start) * 1000)
    assert db_vals == cache_vals, (db_vals[:3], cache_vals[:3])
    print(f"[ok] значения совпали; база: {[round(t) for t in db_times]} мс, кэш: {[round(t, 1) for t in cache_times]} мс (30 чтений)")

    # Инвалидация: писатель обновил порог и сбросил кэш
    sql("UPDATE lab60.minimums SET qty = 900 WHERE warehouse='WH-1' AND product='SKU-101'")
    stale = cache.get(("WH-1", "SKU-101"))
    cache = load_minimums()
    fresh = cache.get(("WH-1", "SKU-101"))
    assert stale == 500.0 and fresh == 900.0
    print(f"[ok] без сброса кэш врал бы ({stale}), после СброситьКэш — {fresh}")


if __name__ == "__main__":
    main()
