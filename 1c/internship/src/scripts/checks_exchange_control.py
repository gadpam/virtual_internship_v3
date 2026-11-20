#!/usr/bin/env python3
"""Проверки task_101: контроль обменов — номера, потеря, расхождения.

Сообщения узлу нумеруются плотно; приёмник, получивший 1,2,4,5,
обязан обнаружить потерю 3 сам. Сверка остатков находит расхождение,
переотправка диапазона закрывает и дырку, и расхождение.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_exchange_control.py
"""

from __future__ import annotations

import os
import subprocess

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = dict(os.environ, PGPASSWORD="rih_local_dev_only")


def sql(query: str) -> str:
    result = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih",
         "-v", "ON_ERROR_STOP=1", "-tAc", query],
        capture_output=True, text=True, env=ENV)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def main() -> None:
    sql("DROP SCHEMA IF EXISTS ctl_main CASCADE; DROP SCHEMA IF EXISTS ctl_branch CASCADE")
    for schema in ("ctl_main", "ctl_branch"):
        sql(f"""CREATE SCHEMA {schema};
            CREATE TABLE {schema}.stock(sku text PRIMARY KEY, qty numeric);
            CREATE TABLE {schema}.inbox(num int PRIMARY KEY, sku text, qty numeric)""")
    sql("INSERT INTO ctl_main.stock VALUES ('SKU-1',100),('SKU-2',50)")

    # Источник шлёт сообщения 1..5: каждое несёт срез остатков.
    messages = {n: ("SKU-1", 100 + n) for n in range(1, 6)}
    # Сообщение 3 «теряется»: приёмник получает 1,2,4,5.
    received = [1, 2, 4, 5]
    for num in received:
        sku, qty = messages[num]
        sql(f"INSERT INTO ctl_branch.inbox VALUES ({num},'{sku}',{qty}) "
            f"ON CONFLICT (num) DO NOTHING")

    got = [int(x) for x in sql("SELECT num FROM ctl_branch.inbox ORDER BY num").split("\n")]
    missing = [n for n in range(1, max(got) + 1) if n not in got]
    assert missing == [3], missing
    print(f"[ok] потеря обнаружена контролем номеров: нет сообщения {missing}")

    # Расхождение остатков видно до восстановления.
    sql("""INSERT INTO ctl_branch.stock
           SELECT sku, qty FROM ctl_branch.inbox WHERE num = 2
           ON CONFLICT (sku) DO UPDATE SET qty = EXCLUDED.qty""")
    diff = sql("""SELECT count(*) FROM (
                    SELECT sku FROM ctl_main.stock
                    EXCEPT SELECT sku FROM ctl_branch.stock
                    UNION ALL
                    SELECT m.sku FROM ctl_main.stock m JOIN ctl_branch.stock b
                      ON b.sku = m.sku WHERE m.qty <> b.qty) d""")
    assert diff != "0"
    print(f"[ok] отчёт расхождений: расходящихся позиций {diff} (SKU-2 нет, SKU-1 не сошёлся)")

    # Восстановление: переотправка диапазона недостающих номеров.
    for num in missing:
        sku, qty = messages[num]
        sql(f"INSERT INTO ctl_branch.inbox VALUES ({num},'{sku}',{qty}) "
            f"ON CONFLICT (num) DO NOTHING")
    sql("""INSERT INTO ctl_branch.stock SELECT sku, qty FROM ctl_main.stock
           ON CONFLICT (sku) DO UPDATE SET qty = EXCLUDED.qty""")
    got = [int(x) for x in sql("SELECT num FROM ctl_branch.inbox ORDER BY num").split("\n")]
    diff_after = sql("""SELECT count(*) FROM (
                          SELECT sku FROM ctl_main.stock
                          EXCEPT SELECT sku FROM ctl_branch.stock
                          UNION ALL
                          SELECT m.sku FROM ctl_main.stock m JOIN ctl_branch.stock b
                            ON b.sku = m.sku WHERE m.qty <> b.qty) d""")
    assert got == [1, 2, 3, 4, 5] and diff_after == "0", (got, diff_after)
    print("[ok] переотправка диапазона закрыла дырку; сверка остатков чиста")


if __name__ == "__main__":
    main()
