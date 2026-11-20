#!/usr/bin/env python3
"""Нагрузка task_63: виртуальные пользователи на аналоге PostgreSQL.

Профиль (из FR task_29): товаровед смотрит остатки склада, отчёт оборотов,
карточку пары. Каждый виртуальный пользователь — отдельный процесс-сеанс
psql, выполняет 10 типовых операций. Уровни: 10/30/50 пользователей.
Стенд: 2 ядра — потолок стенда фиксируется как характеристика, не провал.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_load.py
"""

from __future__ import annotations

import subprocess
import time
from concurrent.futures import ProcessPoolExecutor

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"}
OPS = [
    "SELECT SUM(qty) FROM lab55.movements WHERE warehouse='WH-1'",
    "SELECT SUM(qty) FROM lab55.movements WHERE warehouse='WH-2' AND product='SKU-100'",
    "SELECT grp, SUM(qty) FROM lab55.movements m JOIN (SELECT 'g' grp) x ON true GROUP BY grp LIMIT 1",
]


def one_user(user_no: int) -> tuple[int, int, float]:
    ok, errors, total_ms = 0, 0, 0.0
    for i in range(10):
        sql = OPS[(user_no + i) % len(OPS)]
        start = time.perf_counter()
        proc = subprocess.run([PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih",
                               "-t", "-A", "-c", sql], capture_output=True, text=True, env=ENV)
        total_ms += (time.perf_counter() - start) * 1000
        if proc.returncode == 0:
            ok += 1
        else:
            errors += 1
    return ok, errors, total_ms


def run_level(users: int) -> None:
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=users) as pool:
        results = list(pool.map(one_user, range(users)))
    wall = time.perf_counter() - start
    ok = sum(r[0] for r in results)
    errors = sum(r[1] for r in results)
    avg_ms = sum(r[2] for r in results) / max(ok + errors, 1)
    print(f"[ok] {users:3} польз.: {ok + errors} операций за {wall:.1f} с, "
          f"пропускная {ok / wall:.1f} оп/с, средняя операция {avg_ms:.0f} мс, ошибок {errors}")


def main() -> None:
    for users in (10, 30, 50):
        run_level(users)


if __name__ == "__main__":
    main()
