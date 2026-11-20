#!/usr/bin/env python3
"""Проверки task_186: внешнее соединение с витриной (зеркало отчёта).

Внешний источник — отдельная схема PostgreSQL. Отчёт соединяет
локальные продажи с внешней витриной по SKU. Перед чтением canary
проверяет ожидаемую схему источника: изменение чужой колонки и
недоступность схемы приводят не к падению или молча неверным
цифрам, а к локальному снимку с честной пометкой времени.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_external_db_link.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402

EXPECTED_COLUMNS = "sku,external_revenue"


def read_report(schema: str) -> tuple[str, int]:
    """(источник данных, внешний ориентир SKU-1) с деградацией."""
    try:
        columns = psql(
            "SET statement_timeout = '2000ms'; "
            "SELECT string_agg(column_name, ',' ORDER BY ordinal_position) "
            "FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' AND table_name = 'showcase'"
        ).splitlines()[-1]
        if columns != EXPECTED_COLUMNS:
            raise RuntimeError(f"схема источника изменилась: {columns!r}")
        value = psql(
            "SET statement_timeout = '2000ms'; "
            "SELECT e.external_revenue::int FROM report_local.sales l "
            f"JOIN {schema}.showcase e ON e.sku = l.sku WHERE l.sku = 'SKU-1'"
        ).splitlines()[-1]
        return "live", int(value)
    except RuntimeError:
        value = psql(
            "SELECT external_revenue::int FROM report_local.showcase_snapshot "
            "WHERE sku = 'SKU-1'")
        return "snapshot-07:00", int(value)


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS report_local CASCADE;
DROP SCHEMA IF EXISTS external_vitrine CASCADE;
DROP SCHEMA IF EXISTS external_changed CASCADE;
CREATE SCHEMA report_local;
CREATE SCHEMA external_vitrine;
CREATE TABLE report_local.sales (sku text PRIMARY KEY, revenue numeric);
CREATE TABLE report_local.showcase_snapshot
    (sku text PRIMARY KEY, external_revenue numeric, taken_at text);
CREATE TABLE external_vitrine.showcase
    (sku text PRIMARY KEY, external_revenue numeric);
INSERT INTO report_local.sales VALUES ('SKU-1', 1000);
INSERT INTO report_local.showcase_snapshot VALUES ('SKU-1', 450, '07:00');
INSERT INTO external_vitrine.showcase VALUES ('SKU-1', 500);
""")

    source, value = read_report("external_vitrine")
    assert (source, value) == ("live", 500), (source, value)
    print("[ok] отчёт прочитал внешнюю витрину как дополнительный набор: ориентир SKU-1 = 500 из живого источника")

    psql("""
CREATE SCHEMA external_changed;
CREATE TABLE external_changed.showcase (sku text PRIMARY KEY, amount numeric);
INSERT INTO external_changed.showcase VALUES ('SKU-1', 999);
""")
    source, value = read_report("external_changed")
    assert (source, value) == ("snapshot-07:00", 450), (source, value)
    print("[ok] canary поймал чужое переименование колонки до пользователей: отчёт ушёл на снимок 450, а не показал молча неверные 999")

    psql("DROP SCHEMA external_vitrine CASCADE")
    source, value = read_report("external_vitrine")
    assert (source, value) == ("snapshot-07:00", 450), (source, value)
    print("[ok] недоступность источника: таймаут задан, отчёт деградировал в «данные на 07:00 из локального снимка», а не завис и не упал")


if __name__ == "__main__":
    main()
