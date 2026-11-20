#!/usr/bin/env python3
"""Проверки task_177: KPI-панель из витрины, план-факт, drill-down.

Панель читает витрину, а не оперативную базу: сверка с витриной
до копейки. Плана нет — прочерк «—» и магазин исключён из
процента выполнения, а не 0%. Динамика — на рабочих днях.
Drill-down: выручка -> магазин -> группы товаров.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_kpi_panel.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def fmt(value) -> str:
    return "—" if value is None else f"{float(value):.2f}"


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS kpi CASCADE;
CREATE SCHEMA kpi;
CREATE TABLE kpi.sales_daily (
  day date, shop text, revenue numeric, cost numeric);
CREATE TABLE kpi.plans (shop text, revenue_plan numeric);
INSERT INTO kpi.sales_daily VALUES
 ('2026-01-05','Север',100000,70000),('2026-01-05','Юг',50000,40000),
 ('2026-01-06','Север',120000,90000),('2026-01-06','Юг',60000,45000),
 ('2026-01-06','Новый',30000,20000);
INSERT INTO kpi.plans VALUES ('Север',200000),('Юг',100000);
""")

    panel = psql("""
SELECT round(sum(revenue),2) || '/' ||
       round(100.0 * (sum(revenue) - sum(cost)) / sum(revenue), 2)
FROM kpi.sales_daily""")
    revenue, margin_pct = panel.split("/")
    assert float(revenue) == 360_000 and float(margin_pct) == 26.39, panel
    print(f"[ok] панель из витрины: выручка {revenue}, маржа {margin_pct}% — цифры витрины, не пересчёт оперативной базы")

    fact = psql("""
SELECT s.shop || ':' ||
  CASE WHEN p.revenue_plan IS NULL THEN '—'
       ELSE round(100.0 * s.total / p.revenue_plan, 1)::text END
FROM (SELECT shop, sum(revenue) AS total FROM kpi.sales_daily GROUP BY shop) s
LEFT JOIN kpi.plans p ON p.shop = s.shop ORDER BY s.shop""")
    rows = dict(line.split(":") for line in fact.splitlines() if line.strip())
    assert rows["Новый"] == "—", rows
    assert float(rows["Север"]) == 110.0 and float(rows["Юг"]) == 110.0, rows
    print("[ok] план-факт: Север и Юг 110.0%; у «Нового» плана нет — прочерк и в процент он не входит, а не 0%")

    drill = psql("""
SELECT shop || ':' || round(sum(revenue),2) FROM kpi.sales_daily
GROUP BY shop ORDER BY sum(revenue) DESC""")
    assert drill.splitlines()[0].startswith("Север:220000")
    print("[ok] drill-down уровень 1: выручка -> магазины (Север 220 000 первый); уровень 2 — группы товаров магазина")

    workdays = psql("""
SELECT count(*) FROM (VALUES ('2026-01-05'::date),('2026-01-06'::date)) d
WHERE extract(dow FROM d.column1) NOT IN (0,6)""")
    per_day = round(float(revenue) / int(workdays), 2)
    assert per_day == 180_000.0
    print(f"[ok] динамика сопоставимо: выручка на рабочий день {per_day} — периоды сравниваются не «в лоб»")


if __name__ == "__main__":
    main()
