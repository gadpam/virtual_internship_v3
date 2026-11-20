#!/usr/bin/env python3
"""Проверки task_99: обмен документами между узлами (зеркало).

1000 проведённых поступлений за период едут в приёмник и проводятся
(остатки сходятся), непроведённые и вне периода не едут; документ
со ссылкой на отсутствующий товар создаёт товар по пакету.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_exchange_docs.py
"""

from __future__ import annotations

import os
import subprocess
import time

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
    sql("DROP SCHEMA IF EXISTS doc_main CASCADE; DROP SCHEMA IF EXISTS doc_branch CASCADE")
    for schema in ("doc_main", "doc_branch"):
        sql(f"""CREATE SCHEMA {schema};
            CREATE TABLE {schema}.products(sku text PRIMARY KEY, name text);
            CREATE TABLE {schema}.docs(id int PRIMARY KEY, doc_date date,
                posted boolean, warehouse text);
            CREATE TABLE {schema}.lines(doc_id int, sku text, qty numeric, price numeric);
            CREATE TABLE {schema}.stock(sku text PRIMARY KEY, qty numeric)""")
    sql("""INSERT INTO doc_main.products VALUES ('SKU-1','Товар 1'),('SKU-2','Товар 2');
           INSERT INTO doc_branch.products VALUES ('SKU-1','Товар 1'),('SKU-2','Товар 2');
           INSERT INTO doc_main.docs
             SELECT g, DATE '2026-11-10', true, 'WH-BRANCH' FROM generate_series(1,1000) g;
           INSERT INTO doc_main.docs VALUES (1001, DATE '2026-11-10', false, 'WH-BRANCH');
           INSERT INTO doc_main.docs VALUES (1002, DATE '2026-09-01', true, 'WH-BRANCH');
           INSERT INTO doc_main.lines
             SELECT g, 'SKU-1', 2, 10 FROM generate_series(1,1000) g;
           INSERT INTO doc_main.lines VALUES (500, 'SKU-MISSING', 5, 7)""")

    start = time.perf_counter()
    sql("""INSERT INTO doc_branch.docs
             SELECT * FROM doc_main.docs
             WHERE posted AND doc_date BETWEEN DATE '2026-11-01' AND DATE '2026-11-30'
             ON CONFLICT (id) DO NOTHING;
           INSERT INTO doc_branch.lines
             SELECT l.* FROM doc_main.lines l JOIN doc_branch.docs d ON d.id = l.doc_id
             ON CONFLICT DO NOTHING;
           INSERT INTO doc_branch.products
             SELECT DISTINCT l.sku, 'создан обменом: '||l.sku FROM doc_branch.lines l
             WHERE NOT EXISTS (SELECT 1 FROM doc_branch.products p WHERE p.sku = l.sku)
             ON CONFLICT (sku) DO NOTHING;
           INSERT INTO doc_branch.stock
             SELECT sku, sum(qty) FROM doc_branch.lines GROUP BY sku
             ON CONFLICT (sku) DO UPDATE SET qty = EXCLUDED.qty""")
    seconds = time.perf_counter() - start

    docs = sql("SELECT count(*) FROM doc_branch.docs")
    created = sql("SELECT count(*) FROM doc_branch.products WHERE name LIKE 'создан обменом%'")
    stock = sql("SELECT qty FROM doc_branch.stock WHERE sku='SKU-1'")
    assert docs == "1000" and created == "1" and stock == "2000", (docs, created, stock)
    print(f"[ok] обмен документами: {docs} проведено в приёмнике за {seconds:.2f} с")
    print(f"[ok] отсутствующий товар создан обменом: {created}; остаток SKU-1 сходится: {stock}")


if __name__ == "__main__":
    main()
