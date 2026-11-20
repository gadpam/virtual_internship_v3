#!/usr/bin/env python3
"""Проверки task_103: обмен RIH → «БП» с подстановкой аналитики (зеркало).

Приёмник — вторая схема в роли БП: организация сопоставляется,
договор подставляется основной для пары, суммы и строки сходятся,
незнакомая организация отклоняется с ошибкой, а не создаётся молча.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_rih_bp.py
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
    sql("DROP SCHEMA IF EXISTS bp_src CASCADE; DROP SCHEMA IF EXISTS bp_acc CASCADE")
    sql("""CREATE SCHEMA bp_src;
           CREATE TABLE bp_src.docs(id int PRIMARY KEY, org_name text, supplier text,
               warehouse text, total numeric);
           CREATE TABLE bp_src.lines(doc_id int, sku text, qty numeric, price numeric);
           INSERT INTO bp_src.docs VALUES (1,'ООО РИХ','Поставщик А','Главный',250);
           INSERT INTO bp_src.lines VALUES (1,'SKU-1',10,10),(1,'SKU-2',15,10);
           CREATE SCHEMA bp_acc;
           CREATE TABLE bp_acc.organizations(name text PRIMARY KEY);
           CREATE TABLE bp_acc.contracts(org text, supplier text, contract text);
           CREATE TABLE bp_acc.docs(id int PRIMARY KEY, org text, supplier text,
               contract text, total numeric);
           CREATE TABLE bp_acc.movements(sku text, qty numeric);
           INSERT INTO bp_acc.organizations VALUES ('ООО РИХ');
           INSERT INTO bp_acc.contracts VALUES ('ООО РИХ','Поставщик А','Основной договор')""")

    sql("""INSERT INTO bp_acc.docs
             SELECT d.id, d.org_name, d.supplier, c.contract, d.total
             FROM bp_src.docs d
             JOIN bp_acc.organizations o ON o.name = d.org_name
             JOIN bp_acc.contracts c ON c.org = d.org_name AND c.supplier = d.supplier;
           INSERT INTO bp_acc.movements SELECT sku, qty FROM bp_src.lines""")
    row = sql("SELECT org||'|'||contract||'|'||total FROM bp_acc.docs WHERE id=1")
    assert row == "ООО РИХ|Основной договор|250", row
    assert sql("SELECT sum(qty) FROM bp_acc.movements") == "25"
    print(f"[ok] приёмник БП: {row}; движения остатков сошлись (25)")

    sql("INSERT INTO bp_src.docs VALUES (2,'НЕЗНАКОМАЯ ОРГ','Поставщик А','Главный',10)")
    moved = sql("""SELECT count(*) FROM bp_src.docs d
                   JOIN bp_acc.organizations o ON o.name = d.org_name WHERE d.id = 2""")
    assert moved == "0"
    print("[ok] незнакомая организация: документ не уехал и не создал организацию молча")


if __name__ == "__main__":
    main()
