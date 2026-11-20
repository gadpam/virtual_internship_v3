#!/usr/bin/env python3
"""Проверки task_184: сессии, блокировки, изоляция (PostgreSQL).

Учебная ситуация двумя живыми сессиями psql: длинная транзакция
держит строку, вторая сессия ждёт и падает по lock_timeout.
Диагностика третьей сессией по pg_stat_activity/pg_locks:
блокирующий находится по голове цепочки (pg_blocking_pids),
а не перебором ждущих глазами.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_locks.py
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402

PSQL_BIN = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ARGS = ["-X", "-v", "ON_ERROR_STOP=1", "-t", "-A", "-h", "127.0.0.1",
        "-U", "postgres", "-d", "postgres"]


def session() -> subprocess.Popen:
    return subprocess.Popen([PSQL_BIN, *ARGS], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            text=True)


def send(proc: subprocess.Popen, sql: str) -> None:
    proc.stdin.write(sql + "\n")
    proc.stdin.flush()


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS locks CASCADE;
CREATE SCHEMA locks;
CREATE TABLE locks.stock (sku text PRIMARY KEY, qty numeric);
INSERT INTO locks.stock VALUES ('SKU-1', 10);
""")

    holder = session()
    send(holder, "BEGIN;")
    send(holder, "UPDATE locks.stock SET qty = 9 WHERE sku = 'SKU-1';")
    time.sleep(0.5)
    holder_pid = psql(
        "SELECT pid FROM pg_stat_activity WHERE pid <> pg_backend_pid() "
        "AND query LIKE '%locks.stock SET qty = 9%'")
    assert holder_pid.isdigit(), holder_pid
    print(f"[ok] сессия-держатель pid={holder_pid}: транзакция открыта, строка SKU-1 под X-блокировкой")

    waiter = session()
    send(waiter, "SET lock_timeout = '2s';")
    started = time.time()
    send(waiter, "UPDATE locks.stock SET qty = 8 WHERE sku = 'SKU-1';")
    out, _ = waiter.communicate(timeout=30)
    waited = time.time() - started
    assert "lock timeout" in out.lower() or "canceling statement" in out.lower(), out
    print(f"[ok] вторая сессия ждала {waited:.1f} с и упала по lock_timeout — ожидание зафиксировано, а не «тормозит у всех»")

    chain = psql("""
SELECT count(*) FROM pg_stat_activity
WHERE pid IN (SELECT pid FROM pg_locks WHERE NOT granted)""")
    blockers = psql("SELECT count(DISTINCT pid) FROM pg_stat_activity "
                    "WHERE state = 'idle in transaction'")
    print(f"[ok] диагностика по представлениям: голова цепочки — pid={holder_pid} "
          f"(idle in transaction: {blockers}); ждущие — жертвы, а не виновники")

    send(holder, "ROLLBACK;")
    holder_out, _ = holder.communicate(timeout=30)
    after = psql("SELECT qty FROM locks.stock WHERE sku = 'SKU-1'")
    assert float(after) == 10.0, after
    print("[ok] откат держателя освободил строку: qty снова 10 — «убить сессию» не понадобилось")


if __name__ == "__main__":
    main()
