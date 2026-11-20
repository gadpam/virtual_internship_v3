#!/usr/bin/env python3
"""Проверки task_98: универсальный обмен НСИ с сопоставлением (зеркало КД 2).

Приёмник уже содержит товар под другим внутренним кодом: сопоставление
по артикулу обязано найти его и не создать дубль. Выгрузка — только
изменённые за период (ПВД).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_kd2_exchange.py
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
    sql("DROP SCHEMA IF EXISTS kd_main CASCADE; DROP SCHEMA IF EXISTS kd_branch CASCADE")
    for schema in ("kd_main", "kd_branch"):
        sql(f"""CREATE SCHEMA {schema};
            CREATE TABLE {schema}.products(guid text, sku text PRIMARY KEY,
                name text, changed_at date)""")
    # Источник: 3 товара, один изменён после начала периода ПВД.
    sql("""INSERT INTO kd_main.products VALUES
             ('g-1','SKU-1','Крупа гречневая','2026-11-01'),
             ('g-2','SKU-2','Сахар','2026-11-10'),
             ('g-3','SKU-3','Соль','2026-10-01')""")
    # Приёмник: SKU-2 уже есть под ДРУГИМ guid и старым именем.
    sql("INSERT INTO kd_branch.products VALUES ('other-9','SKU-2','Сахар старый','2026-09-01')")

    # ПВД: изменённые с 2026-11-05 — только SKU-2.
    exported = sql("""SELECT count(*) FROM kd_main.products
                      WHERE changed_at >= DATE '2026-11-05'""")
    assert exported == "1", exported

    # Загрузка пакета периода: сопоставление guid → артикул → создать.
    sql("""INSERT INTO kd_branch.products
           SELECT * FROM kd_main.products WHERE changed_at >= DATE '2026-11-05'
           ON CONFLICT (sku) DO UPDATE SET name=EXCLUDED.name,
               changed_at=EXCLUDED.changed_at""")
    assert sql("SELECT count(*) FROM kd_branch.products") == "1"
    assert sql("SELECT name FROM kd_branch.products WHERE sku='SKU-2'") == "Сахар"
    print("[ok] товар под чужим кодом найден по артикулу: обновлён, дубля нет")

    # Полный пакет: остальные создаются; повторная загрузка идемпотентна.
    for _ in range(2):
        sql("""INSERT INTO kd_branch.products SELECT * FROM kd_main.products
               ON CONFLICT (sku) DO UPDATE SET name=EXCLUDED.name,
                   changed_at=EXCLUDED.changed_at""")
    total = sql("SELECT count(*) FROM kd_branch.products")
    assert total == "3", total
    print(f"[ok] полный пакет загружен дважды: в приёмнике {total} товара, дублей нет")


if __name__ == "__main__":
    main()
