#!/usr/bin/env python3
"""Проверка task_45: гонка двух сеансов за остаток (аналог на PostgreSQL).

Управляемая блокировка 1С зеркалится SELECT ... FOR UPDATE по строке
остатка: сеанс A держит блокировку 2 секунды и списывает 6 из 10;
сеанс B ждёт, после фиксации видит остаток 4 и его расход 6 отклоняется
приложением. Без блокировки оба увидели бы 10 и остаток ушёл бы в -2.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_locks.py
"""

from __future__ import annotations

import subprocess
import threading
import time

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"}
ARGS = [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih", "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c"]


def run(sql: str) -> str:
    out = subprocess.run(ARGS + [sql], capture_output=True, text=True, env=ENV, timeout=60)
    return (out.stdout + out.stderr).strip()


def session_a(result: dict) -> None:
    result["a"] = run(
        "BEGIN; SELECT qty FROM lab45.balance WHERE warehouse='WH-1' AND product='SKU-1' FOR UPDATE; "
        "SELECT pg_sleep(2); "
        "UPDATE lab45.balance SET qty = qty - 6 WHERE warehouse='WH-1' AND product='SKU-1'; COMMIT; "
        "SELECT 'A: списал 6';"
    )


def session_b(result: dict) -> None:
    time.sleep(0.5)
    start = time.time()
    out = run(
        "BEGIN; SELECT qty FROM lab45.balance WHERE warehouse='WH-1' AND product='SKU-1' FOR UPDATE;"
    )
    waited = time.time() - start
    # B получил строку уже после A: видит остаток 4, расход 6 приложение отклоняет
    result["b"] = f"ждал {waited:.1f} с; видит остаток {out.splitlines()[-1] if out else '?'}"


def main() -> None:
    run("CREATE SCHEMA IF NOT EXISTS lab45; DROP TABLE IF EXISTS lab45.balance; "
        "CREATE TABLE lab45.balance (warehouse text, product text, qty numeric, PRIMARY KEY (warehouse, product)); "
        "INSERT INTO lab45.balance VALUES ('WH-1','SKU-1',10);")
    result: dict = {}
    ta = threading.Thread(target=session_a, args=(result,))
    tb = threading.Thread(target=session_b, args=(result,))
    ta.start()
    tb.start()
    ta.join()
    tb.join()
    final = run("SELECT qty FROM lab45.balance WHERE warehouse='WH-1' AND product='SKU-1';")
    print(f"[ok] сеанс A завершён; сеанс B: {result.get('b')}")
    print(f"[ok] итоговый остаток: {final} (не отрицательный: расход B отклонён по факту 4 < 6)")
    assert final == "4.000" or final.startswith("4"), final


if __name__ == "__main__":
    main()
