#!/usr/bin/env python3
"""Проверки task_97: первый обмен между двумя узлами (зеркало плана обмена).

Узлы — PG-схемы node_main (ЦО, master НСИ) и node_branch (филиал).
Обмен: НСИ полностью по регистрации изменений, документы — только
склада филиала (фильтр топологии), проведённые.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_exchange_topology.py
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
    sql("DROP SCHEMA IF EXISTS node_main CASCADE; DROP SCHEMA IF EXISTS node_branch CASCADE")
    for schema in ("node_main", "node_branch"):
        sql(f"""CREATE SCHEMA {schema};
            CREATE TABLE {schema}.products(sku text PRIMARY KEY, name text,
                price numeric, changed_at timestamptz);
            CREATE TABLE {schema}.docs(id int PRIMARY KEY, warehouse text,
                posted boolean, total numeric)""")
    sql("""INSERT INTO node_main.products
           SELECT 'SKU-'||g, 'Товар '||g, 10+g, now() FROM generate_series(1,50) g;
           INSERT INTO node_main.docs VALUES
             (1,'WH-BRANCH',true,100),(2,'WH-CENTRAL',true,200),(3,'WH-BRANCH',false,300)""")

    # Регистрация изменений: всё, что изменилось после метки узла (первый обмен — всё).
    moved_products = sql("""INSERT INTO node_branch.products
        SELECT * FROM node_main.products
        ON CONFLICT (sku) DO UPDATE SET name=EXCLUDED.name, price=EXCLUDED.price,
            changed_at=EXCLUDED.changed_at
        RETURNING 1""").count("\n") + 1
    # Фильтр топологии: филиалу — только его склады и только проведённые.
    sql("""INSERT INTO node_branch.docs
           SELECT * FROM node_main.docs WHERE warehouse='WH-BRANCH' AND posted
           ON CONFLICT (id) DO NOTHING""")

    branch_products = sql("SELECT count(*) FROM node_branch.products")
    branch_docs = sql("SELECT count(*) FROM node_branch.docs")
    assert branch_products == "50" and branch_docs == "1", (branch_products, branch_docs)
    assert sql("SELECT count(*) FROM node_branch.docs WHERE warehouse='WH-CENTRAL'") == "0"
    print(f"[ok] первый обмен: НСИ {branch_products} позиций, документов филиала {branch_docs}")
    print("[ok] фильтр топологии: документы центрального склада в филиал не уехали")


if __name__ == "__main__":
    main()
