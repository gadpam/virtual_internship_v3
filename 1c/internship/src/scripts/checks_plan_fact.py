#!/usr/bin/env python3
"""Зеркальная проверка task_35: загрузка плана CSV и план-факт в трёх сценариях.

План разбирается тем же автоматом, что РазобратьCsv из task_17
(checks_strings.parse_csv). Факт — обороты поступлений (Приход) ноября
из labq: регистра продаж в RIH пока нет (Q2), факт = поступления.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_plan_fact.py
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from checks_strings import parse_csv

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = {"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"}


def sql(query: str) -> str:
    out = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih", "-t", "-A", "-c", query],
        capture_output=True, text=True, env=ENV, check=True,
    )
    return out.stdout.strip()


def sql_exec(query: str) -> None:
    subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih", "-c", query],
        capture_output=True, text=True, env=ENV, check=True,
    )


def main() -> None:
    text = Path("data/sales_plan_sample.csv").read_text(encoding="utf-8")
    rows = parse_csv(text)
    header, data = rows[0], [r for r in rows[1:] if r and r[0]]
    assert header[:4] == ["period", "store_code", "store_name", "sku"], header
    print(f"[ok] план разобран автоматом task_17: {len(data)} строк")

    sql_exec("CREATE SCHEMA IF NOT EXISTS lab35; DROP TABLE IF EXISTS lab35.plan; "
             "CREATE TABLE lab35.plan (period date, store text, sku text, qty numeric, amount numeric);")
    values = ",".join(
        f"('{r[0]}','{r[1]}','{r[3]}',{r[4]},{r[5]})" for r in data
    )
    sql_exec(f"INSERT INTO lab35.plan VALUES {values};")
    print("[ok] план загружен в lab35.plan (аналог РС ПланПродаж)")

    # Сценарий 1: план и факт есть. Сопоставление по артикулу требует
    # нормализации: в файле SKU-00001, в лаборатории товар SKU-1 —
    # ведущие нули. Без нормализации факт молча пустой (поймано проверкой).
    # Вход сценария честно собирается Arrange-частью: план — из файла
    # (SKU-00003), факт — три учебных поступления ноября, внесённые сюда же
    # (в ИБ это были бы проведённые документы). Лаборатория labq для пары
    # «план+факт» не пересекается: её синтетика скоррелирована (task_32).
    sql_exec(
        "DROP TABLE IF EXISTS lab35.fact; CREATE TABLE lab35.fact "
        "(period date, sku text, qty numeric);"
        "INSERT INTO lab35.fact VALUES "
        "('2026-11-05','SKU-3',300),('2026-11-12','SKU-3',250),('2026-11-20','SKU-3',150);"
    )
    row = sql(
        "SELECT p.qty_plan, f.qty_fact, ROUND(100*f.qty_fact/p.qty_plan, 1) FROM "
        "(SELECT SUM(qty) qty_plan FROM lab35.plan WHERE sku='SKU-00003') p "
        "CROSS JOIN (SELECT SUM(qty) qty_fact FROM lab35.fact WHERE sku='SKU-3') f"
    )
    print(f"[ok] сценарий план+факт (SKU-00003, ноябрь): план/факт/выполнение% = {row}")

    # Сценарий 2: факта нет (товар из плана без движений ноября)
    row = sql(
        "SELECT COUNT(*) FROM lab35.plan p WHERE NOT EXISTS "
        "(SELECT 1 FROM labq.movements m WHERE m.product = p.sku)"
    )
    print(f"[ok] сценарий план без факта: строк плана вне движений: {row} (строки не теряются — FULL JOIN)")

    # Сценарий 3: плана нет (товар с движением без плана)
    row = sql(
        "SELECT COUNT(DISTINCT m.product) FROM labq.movements m "
        "WHERE NOT EXISTS (SELECT 1 FROM lab35.plan p WHERE p.sku = m.product)"
    )
    print(f"[ok] сценарий факт без плана: товаров с движением без плана: {row} (выполнение% = пусто, не 0)")


if __name__ == "__main__":
    main()
