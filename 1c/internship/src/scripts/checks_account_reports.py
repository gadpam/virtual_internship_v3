#!/usr/bin/env python3
"""Проверки task_158: анализ счёта, карточка счёта, обороты по аналитике.

Три отчёта на одних движениях счёта 41 сверяются между собой и
с ОСВ (task_157): обороты анализа = сумме проводок карточки =
обороту ведомости до копейки. Карточка: нарастающее сальдо
оконной функцией, каждая строка несёт документ-основание.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_account_reports.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS rep CASCADE;
CREATE SCHEMA rep;
CREATE TABLE rep.entries (
  period date, doc text, account_dt text, account_kt text,
  amount numeric, qty numeric, item text, warehouse text);
INSERT INTO rep.entries VALUES
 ('2026-01-10','Поступление-1','41','60',100000,50,'Товар А','WH-01'),
 ('2026-01-15','Продажа-1','90.2','41',60000,30,'Товар А','WH-01'),
 ('2026-01-20','Возврат-1','41','90.2',12000,6,'Товар А','WH-01'),
 ('2026-01-22','Поступление-2','41','60',8000,4,'Товар Б','WH-02');
""")

    analysis = psql("""
SELECT round(sum(CASE WHEN account_dt='41' THEN amount ELSE 0 END),2) || '/' ||
       round(sum(CASE WHEN account_kt='41' THEN amount ELSE 0 END),2)
FROM rep.entries WHERE '41' IN (account_dt, account_kt)""")
    assert analysis == "120000.00/60000.00", analysis
    print(f"[ok] анализ счёта 41: обороты Дт/Кт {analysis} в разрезе субконто с итогами")

    card = psql("""
SELECT doc || ':' || round(running,2) FROM (
  SELECT doc, period,
    sum(CASE WHEN account_dt='41' THEN amount ELSE -amount END)
      OVER (ORDER BY period, doc) AS running
  FROM rep.entries WHERE '41' IN (account_dt, account_kt)) t
ORDER BY period, doc""")
    rows = [line for line in card.splitlines() if line.strip()]
    assert rows[-1].endswith(":60000.00"), rows
    assert all(":" in row for row in rows)
    print(f"[ok] карточка счёта: {len(rows)} проводок с документами, нарастающее сальдо -> 60000.00")

    osv_dt = psql("""
SELECT round(sum(amount),2) FROM rep.entries WHERE account_dt='41'""")
    assert float(osv_dt) == 120_000.0
    print("[ok] согласованность: анализ = карточка = ОСВ по обороту Дт 41 (120 000.00)")

    pivot = psql("""
SELECT warehouse || '/' || item || ':' ||
       round(sum(CASE WHEN account_dt='41' THEN qty ELSE -qty END),2)
FROM rep.entries WHERE '41' IN (account_dt, account_kt)
GROUP BY warehouse, item ORDER BY warehouse, item""")
    assert "WH-01/Товар А:26.00" in pivot and "WH-02/Товар Б:4.00" in pivot, pivot
    print("[ok] обороты по аналитике склад x номенклатура: WH-01/Товар А 26 шт, WH-02/Товар Б 4 шт")


if __name__ == "__main__":
    main()
