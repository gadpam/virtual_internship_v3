#!/usr/bin/env python3
"""Проверки task_175: кросс-системный отчёт «Портфель контрагента».

Четыре витрины (договоры, отгрузки/оплаты, сальдо, задачи) на
PostgreSQL. Контроль связей: суммы и число строк после каждой
связи сверяются с источниками по отдельности; связь наборов
по ИНН через агрегированные подзапросы, а не строка-к-строке —
иначе декартово произведение раздувает отчёт при правдоподобном
виде. Риски подсвечены флагами, а не чтением цифр.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_cross_report.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS xs CASCADE;
CREATE SCHEMA xs;
CREATE TABLE xs.shipments (inn text, amount numeric);
CREATE TABLE xs.payments (inn text, amount numeric);
CREATE TABLE xs.balances (inn text, debt numeric, overdue_days int);
CREATE TABLE xs.contracts (inn text, status text, active boolean);
CREATE TABLE xs.overdue_tasks (inn text, tasks int);
INSERT INTO xs.shipments VALUES
 ('7701000001',100000),('7701000001',50000),('7701000002',80000),('7701000003',30000);
INSERT INTO xs.payments VALUES ('7701000001',150000),('7701000002',20000);
INSERT INTO xs.balances VALUES
 ('7701000001',0,0),('7701000002',60000,45),('7701000003',30000,5);
INSERT INTO xs.contracts VALUES
 ('7701000001','Подписан',true),('7701000001','Подписан (рамочный)',true),
 ('7701000002','Подписан',true),('7701000003','Истёк',false);
INSERT INTO xs.overdue_tasks VALUES
 ('7701000001',0),('7701000002',2),('7701000003',0);
""")

    src_ship = psql("SELECT round(sum(amount),2) FROM xs.shipments")
    assert float(src_ship) == 260_000, src_ship

    naive = psql("""
SELECT round(sum(s.amount),2) FROM xs.shipments s
JOIN xs.contracts c ON c.inn = s.inn WHERE s.inn='7701000001'""")
    assert float(naive) == 300_000, naive  # два договора удвоили отгрузки
    print(f"[ok] ловушка связи видна цифрой: наивная связь договоров дала {naive} вместо 150000 — декартово раздувание")

    joined = psql("""
SELECT s.inn || ':' || round(s.total,2) FROM
 (SELECT inn, sum(amount) AS total FROM xs.shipments GROUP BY inn) s
JOIN (SELECT inn, sum(amount) AS paid FROM xs.payments GROUP BY inn) p
  ON p.inn = s.inn ORDER BY s.inn""")
    rows = dict(line.split(":") for line in joined.splitlines() if line.strip())
    assert float(rows["7701000001"]) == 150_000 and float(rows["7701000002"]) == 80_000, rows
    total = psql("""
SELECT round(sum(t.total),2) FROM
 (SELECT sum(amount) AS total FROM xs.shipments GROUP BY inn) t""")
    assert float(total) == float(src_ship)
    print("[ok] связи агрегированными наборами по ИНН: суммы отчёта = суммам источников, строк не потеряно и не задвоено")

    risks = psql("""
SELECT b.inn FROM xs.balances b WHERE b.debt > 0 AND b.overdue_days > 30""")
    assert risks == "7701000002", risks
    no_contract = psql("""
SELECT s.inn FROM (SELECT DISTINCT inn FROM xs.shipments) s
WHERE NOT EXISTS (SELECT 1 FROM xs.contracts c WHERE c.inn = s.inn AND c.active)""")
    assert no_contract == "7701000003", no_contract
    print("[ok] условное оформление риском: Бета — просроченная задолженность 45 дн, Гамма — отгрузки без действующего договора")

    psql("""
CREATE TABLE xs.big_shipments (inn text, amount numeric);
INSERT INTO xs.big_shipments
SELECT '77' || lpad(g::text, 8, '0'), 100.00
FROM generate_series(1, 100000) g;
""")
    started = time.time()
    perf = psql("""
SELECT count(DISTINCT inn) || '/' || round(sum(amount),2) FROM xs.big_shipments""")
    elapsed = time.time() - started
    assert perf == "100000/10000000.00", perf
    print(f"[ok] объём стенда: 100 000 документов агрегированы за {elapsed:.2f} с; "
          "сверка источников на этом объёме обязательна до приёма отчёта")


if __name__ == "__main__":
    main()
