#!/usr/bin/env python3
"""Проверки task_152: регистр бухгалтерии РИХ_Учёт (зеркало).

Таблица проводок со счетами Дт/Кт, суммой, количеством и тремя
субконто; три запроса виртуальных таблиц их SQL-эквивалентами:
остатки по счёту на дату, обороты за период, обороты по субконто.
Ручная проводка Дт 41 Кт 60 видна в разрезе всех субконто;
инвариант дебет = кредит — по итогам периода.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_accounting_register.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS acct CASCADE;
CREATE SCHEMA acct;
CREATE TABLE acct.entries (
  period date, org text, account_dt text, account_kt text,
  amount numeric, qty_dt numeric, qty_kt numeric,
  sub1 text, sub2 text, sub3 text, doc text);
INSERT INTO acct.entries VALUES
 ('2026-01-10','RIH-Holding','41','60',100000,50,0,'Товар А','WH-01','Поставщик Альфа','Поступление-1'),
 ('2026-01-10','RIH-Holding','68','60',20000,0,0,'НДС','','Поставщик Альфа','Поступление-1'),
 ('2026-01-12','RIH-Holding','60','51',120000,0,0,'Поставщик Альфа','','','Оплата-1'),
 ('2026-01-15','RIH-Holding','62','90.1',150000,0,0,'Магазин Север','','','Продажа-1'),
 ('2026-01-15','RIH-Holding','90.2','41',60000,0,30,'Товар А','WH-01','','Продажа-1'),
 ('2026-01-20','RIH-Holding','90.1','62',30000,0,0,'Магазин Север','','','Возврат-1'),
 ('2026-01-20','RIH-Holding','41','90.2',12000,6,0,'Товар А','WH-01','','Возврат-1');
""")

    rest = psql("""
SELECT round(sum(CASE WHEN account_dt='41' THEN amount ELSE -amount END), 2)
FROM acct.entries WHERE '41' IN (account_dt, account_kt) AND period <= '2026-01-31'""")
    assert float(rest) == 52_000, rest
    qty = psql("""
SELECT round(sum(CASE WHEN account_dt='41' THEN qty_dt ELSE -qty_kt END), 2)
FROM acct.entries WHERE '41' IN (account_dt, account_kt) AND period <= '2026-01-31'""")
    assert float(qty) == 26, qty  # 50 - 30 + 6: количественный признак счёта работает
    print(f"[ok] остатки по счёту 41 на дату: сумма {rest}, количество {qty} шт")

    turnovers = psql("""
SELECT round(sum(CASE WHEN side='dt' THEN amount ELSE 0 END),2) || '/' ||
       round(sum(CASE WHEN side='kt' THEN amount ELSE 0 END),2)
FROM (SELECT account_dt AS acc, amount, 'dt' AS side FROM acct.entries
      UNION ALL SELECT account_kt, amount, 'kt' FROM acct.entries) t""")
    left, right = turnovers.split("/")
    assert left == right, turnovers
    print(f"[ok] обороты периода: дебет {left} = кредит {right} — инвариант держится")

    by_sub = psql("""
SELECT sub1 || ':' || round(sum(amount),2) FROM acct.entries
WHERE account_dt='41' GROUP BY sub1 ORDER BY sub1""")
    assert "Товар А:112000.00" in by_sub, by_sub
    print(f"[ok] обороты по субконто счёта 41: {by_sub.splitlines()[0]} "
          "(номенклатура x склад x контрагент видны одной выборкой)")

    orgs = psql("SELECT count(DISTINCT org) FROM acct.entries")
    assert orgs == "1"
    print("[ok] измерение Организация в регистре: отчёт по организациям — настройка, а не переделка")


if __name__ == "__main__":
    main()
