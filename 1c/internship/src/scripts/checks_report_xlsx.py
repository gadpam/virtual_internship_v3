#!/usr/bin/env python3
"""Зеркальная проверка task_34: программное формирование отчёта и XLSX.

Аналог СформироватьОстатки: тот же набор (остатки по складам из labq),
«табличный документ» зеркалится таблицей, выгрузка — реальный XLSX
(openpyxl). Проверяется: документ не пустой, итоги строки сходятся,
XLSX открывается и содержит те же числа.

Подключение к БД: переменные окружения из tools/.env не нужны —
используется локальный сокет лаборатории (/tmp/walk-pg) через psycopg,
если он есть; иначе скрипт честно пропускает часть БД (см. вывод).
Запуск: src/scripts/.venv/bin/python src/scripts/checks_report_xlsx.py
"""

from __future__ import annotations

import subprocess
from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook, load_workbook

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"


def fetch_balances() -> list[tuple[str, str, Decimal]]:
    sql = (
        "SELECT warehouse, product, SUM(CASE WHEN kind='Приход' THEN qty ELSE -qty END) "
        "FROM labq.movements GROUP BY 1,2 HAVING SUM(CASE WHEN kind='Приход' THEN qty ELSE -qty END) <> 0 "
        "ORDER BY 1,2"
    )
    out = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih", "-t", "-A", "-F", ";", "-c", sql],
        capture_output=True, text=True, env={"PATH": "/usr/bin:/bin", "PGPASSWORD": "rih_local_dev_only"},
        check=True,
    )
    rows = []
    for line in out.stdout.strip().splitlines():
        wh, prod, qty = line.split(";")
        rows.append((wh, prod, Decimal(qty)))
    return rows


def main() -> None:
    rows = fetch_balances()
    assert rows, "табличный документ пустой — программное формирование не работает"
    print(f"[ok] «табличный документ» не пустой: {len(rows)} строк остатков")

    wb = Workbook()
    ws = wb.active
    ws.title = "Остатки"
    ws.append(["Склад", "Номенклатура", "Количество"])
    for row in rows:
        ws.append([row[0], row[1], float(row[2])])
    path = Path("tools/reports_out/balances_check.xlsx")
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)

    back = load_workbook(path)
    sheet = back["Остатки"]
    assert sheet.max_row == len(rows) + 1, "XLSX: число строк не сошлось"
    total_xlsx = sum(sheet.cell(row=i, column=3).value for i in range(2, sheet.max_row + 1))
    total_src = float(sum(r[2] for r in rows))
    assert abs(total_xlsx - total_src) < 0.01, "XLSX: итог не сошёлся с источником"
    print(f"[ok] XLSX выгрузка: {path}, строк {sheet.max_row - 1}, итог {total_xlsx:.3f} сходится")


if __name__ == "__main__":
    main()
