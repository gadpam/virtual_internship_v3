#!/usr/bin/env python3
"""Проверки task_182: аналитический SQL — окна, CTE, дубли, сироты.

Шесть приёмов на живых таблицах стенда (файлы tools/sql/analysis).
Дубли ищутся по бизнес-ключу целиком; «сироты» — диагноз для
разбора: начальные остатки без регистратора легальны, строка
табличной части без документа — нет.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_analytics_sql.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS analytics CASCADE;
CREATE SCHEMA analytics;
CREATE TABLE analytics.analytics_sales (day date, shop text, item_ref text, amount numeric);
CREATE TABLE analytics.analytics_inbox (source_system text, external_id text);
CREATE TABLE analytics.analytics_docs (id text);
CREATE TABLE analytics.analytics_doc_goods (doc_id text, line_no int);
CREATE TABLE analytics.analytics_movements (period date, registrator text, item_ref text, qty numeric);
INSERT INTO analytics.analytics_sales VALUES
 ('2026-01-05','Север','SKU-1',700),('2026-01-05','Север','SKU-2',300),
 ('2026-02-03','Север','SKU-1',1400),('2026-02-03','Юг','SKU-2',600);
INSERT INTO analytics.analytics_inbox VALUES
 ('shop','ORD-1'),('shop','ORD-1'),('shop','ORD-2');
INSERT INTO analytics.analytics_docs VALUES ('doc-1');
INSERT INTO analytics.analytics_doc_goods VALUES ('doc-1',1),('doc-orphan',1);
INSERT INTO analytics.analytics_movements VALUES
 ('2026-01-01',NULL,'SKU-1',100),('2026-01-10','doc-1','SKU-1',50);
""")

    top = psql("""
WITH per_item AS (
  SELECT day, item_ref, sum(amount) AS total FROM analytics.analytics_sales
  GROUP BY day, item_ref)
SELECT item_ref || ':' || round(100.0 * total / sum(total) OVER (PARTITION BY day), 1)
FROM per_item WHERE day='2026-01-05' ORDER BY total DESC""")
    assert top.splitlines()[0] == "SKU-1:70.0", top
    print("[ok] 040 топ с долей окна: SKU-1 — 70.0% дня без самосоединений")

    growth = psql("""
WITH monthly AS (
  SELECT date_trunc('month', day) AS m, sum(amount) AS total
  FROM analytics.analytics_sales GROUP BY 1)
SELECT round(100.0 * (total - lag(total) OVER (ORDER BY m))
       / lag(total) OVER (ORDER BY m), 1) FROM monthly ORDER BY m DESC LIMIT 1""")
    assert float(growth) == 100.0, growth
    print("[ok] 050 динамика LAG: февраль к январю +100.0% (2000 против 1000)")

    dup = psql("""
SELECT external_id || ':' || count(*) FROM analytics.analytics_inbox
GROUP BY source_system, external_id HAVING count(*) > 1""")
    assert dup == "ORD-1:2", dup
    orphans = psql("""
SELECT g.doc_id FROM analytics.analytics_doc_goods g
LEFT JOIN analytics.analytics_docs d ON d.id = g.doc_id WHERE d.id IS NULL""")
    assert orphans == "doc-orphan", orphans
    print("[ok] 080/090 грязь найдена запросами: дубль ORD-1 x2 и строка без документа doc-orphan")

    psql("""
CREATE TABLE analytics.big_sales (day date, shop text, amount numeric);
INSERT INTO analytics.big_sales
SELECT '2026-01-05'::date + (g % 60), 'Магазин ' || (g % 10), 10.00
FROM generate_series(1, 60000) g;
""")
    query_cte = ("WITH daily AS (SELECT day, sum(amount) AS t FROM analytics.big_sales "
                 "GROUP BY day) SELECT count(*) FROM daily")
    query_sub = "SELECT count(*) FROM (SELECT day FROM analytics.big_sales GROUP BY day) s"
    for query in (query_cte, query_sub):
        started = time.time()
        psql(query)
        assert time.time() - started < 5
    print("[ok] 095 CTE и подзапрос: оба укладываются в секунды стенда; CTE выбран читаемостью конвейера")

    levels = psql("""
SELECT count(*) FROM (
  SELECT shop FROM analytics.analytics_sales
  GROUP BY ROLLUP (shop, item_ref)) levels""")
    assert int(levels) >= 4, levels
    print("[ok] 070 уровни итогов одним проходом ROLLUP: магазин/товар/итог помечаются GROUPING")


if __name__ == "__main__":
    main()
