#!/usr/bin/env python3
"""Проверки task_106: коллизия автономной работы узлов РИБ (зеркало).

Оба узла изменили один товар после метки синхронизации: обмен обязан
увидеть коллизию, применить master-правило центра для НСИ и оставить
след в протоколе, а не затереть одну из правок молча.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_rib_collision.py
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
    sql("DROP SCHEMA IF EXISTS rib_main CASCADE; DROP SCHEMA IF EXISTS rib_branch CASCADE")
    for schema in ("rib_main", "rib_branch"):
        sql(f"""CREATE SCHEMA {schema};
            CREATE TABLE {schema}.products(sku text PRIMARY KEY, name text,
                price numeric, version int, changed_at timestamptz);
            CREATE TABLE {schema}.sync_mark(sku text PRIMARY KEY, version int);
            CREATE TABLE {schema}.conflicts(sku text, field text, main_value text,
                branch_value text, resolution text)""")
    sql("""INSERT INTO rib_main.products VALUES ('SKU-1','Крупа',100,1,now());
           INSERT INTO rib_branch.products SELECT * FROM rib_main.products;
           INSERT INTO rib_main.sync_mark VALUES ('SKU-1',1);
           INSERT INTO rib_branch.sync_mark VALUES ('SKU-1',1)""")

    # Автономная работа: центр переименовал, магазин поставил цену акции.
    sql("UPDATE rib_main.products SET name='Крупа гречневая', version=2, changed_at=now() WHERE sku='SKU-1'")
    sql("UPDATE rib_branch.products SET price=79, version=2, changed_at=now() WHERE sku='SKU-1'")

    # Обмен: изменились оба после метки (version > sync_mark) — коллизия.
    collisions = sql("""SELECT count(*) FROM rib_main.products m
                        JOIN rib_branch.products b ON b.sku = m.sku
                        JOIN rib_main.sync_mark sm ON sm.sku = m.sku
                        WHERE m.version > sm.version AND b.version > sm.version""")
    assert collisions == "1"
    print("[ok] коллизия обнаружена: объект изменён в обоих узлах после метки")

    # Разрешение: НСИ — master центр (имя центра), цена склада — за магазином.
    sql("""INSERT INTO rib_main.conflicts
             SELECT m.sku, 'name/price', m.name||'/'||m.price, b.name||'/'||b.price,
                    'имя — центр (master НСИ), цена акции — магазин до конца акции'
             FROM rib_main.products m JOIN rib_branch.products b ON b.sku = m.sku;
           UPDATE rib_branch.products b SET name = m.name
             FROM rib_main.products m WHERE m.sku = b.sku;
           UPDATE rib_main.sync_mark SET version = 2;
           UPDATE rib_branch.sync_mark SET version = 2""")
    name = sql("SELECT name FROM rib_branch.products WHERE sku='SKU-1'")
    price = sql("SELECT price FROM rib_branch.products WHERE sku='SKU-1'")
    protocol = sql("SELECT count(*) FROM rib_main.conflicts")
    assert name == "Крупа гречневая" and price == "79" and protocol == "1"
    print(f"[ok] разрешение: имя центра '{name}', цена магазина {price} сохранена, протокол коллизий: {protocol}")


if __name__ == "__main__":
    main()
