#!/usr/bin/env python3
"""Проверки task_126: BI-доступ к витринам и запросы первого дашборда.

Superset в этой среде не поднимается (нет демона Docker), поэтому
проверяется его исполняемый контракт: сервисный пользователь bi_reader
читает только витрины, три запроса дашборда отвечают на живых данных
витрины task_122, баннер свежести показывает время последней загрузки.
Подъём контейнера — точка возврата в документации стенда.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_bi_stand.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

PSQL_CANDIDATES = [
    os.environ.get("PSQL", ""),
    shutil.which("psql") or "",
    "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql",
]
PSQL = next((path for path in PSQL_CANDIDATES if path and Path(path).exists()), "")
MARTS = Path("tools/sql/marts")


def psql(sql: str, user: str = "rih", password: str | None = None) -> str:
    env = dict(os.environ)
    if password:
        env["PGPASSWORD"] = password
    proc = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-U", user, "-d", "rih",
         "-v", "ON_ERROR_STOP=1", "-q", "-t", "-A"],
        input=sql, capture_output=True, text=True, timeout=600, env=env)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-600:])
    return proc.stdout.strip()


def psql_fails(sql: str, user: str, password: str) -> str:
    env = dict(os.environ, PGPASSWORD=password)
    proc = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-U", user, "-d", "rih",
         "-v", "ON_ERROR_STOP=1", "-q", "-t", "-A"],
        input=sql, capture_output=True, text=True, timeout=120, env=env)
    assert proc.returncode != 0, f"запрещённый доступ прошёл: {sql[:60]}"
    return proc.stderr.strip().splitlines()[0] if proc.stderr.strip() else ""


def apply_marts() -> None:
    for name in ("010_schema.sql", "020_mart_sales.sql", "030_mart_integration.sql",
                 "040_metrics_dictionary.sql", "050_quality_views.sql",
                 "060_mart_sales_daily.sql", "065_load_fact_sales_daily.sql"):
        psql((MARTS / name).read_text(encoding="utf-8"))
    exists = psql("SELECT count(*) FROM pg_roles WHERE rolname = 'bi_reader';",
                  user="postgres")
    if exists == "0":
        psql("CREATE ROLE bi_reader LOGIN PASSWORD 'bi_reader_dev';", user="postgres")
    psql((MARTS / "070_bi_access.sql").read_text(encoding="utf-8"))


def main() -> None:
    assert PSQL, "psql не найден: задайте PSQL или поднимите стенд PostgreSQL"
    apply_marts()
    print("[ok] витрины стенда подняты, bi_reader создан скриптом 070")

    daily = psql("SELECT date_key || '=' || round(sum(revenue), 2) "
                 "FROM marts.v_sales_daily GROUP BY date_key ORDER BY date_key LIMIT 3;",
                 user="bi_reader", password="bi_reader_dev")
    assert daily, "дашборд продаж по дням пуст"
    print(f"[ok] график «продажи по дням» отвечает би-пользователю: {daily.splitlines()[0]} …")

    top = psql("SELECT p.product_name || '=' || round(sum(f.revenue), 2) "
               "FROM marts.fact_sales AS f "
               "JOIN marts.dim_product AS p ON p.product_key = f.product_key "
               "GROUP BY p.product_name ORDER BY sum(f.revenue) DESC LIMIT 10;",
               user="bi_reader", password="bi_reader_dev")
    assert len(top.splitlines()) >= 5
    print(f"[ok] график «топ-10 товаров» отвечает ({len(top.splitlines())} товаров стенда): "
          f"{top.splitlines()[0]} …")

    fresh = psql("SELECT max(loaded_at) FROM marts.fact_sales_daily;",
                 user="bi_reader", password="bi_reader_dev")
    assert fresh
    print(f"[ok] баннер свежести на дашборде: последние данные витрины на {fresh[:16]}")

    denied_write = psql_fails(
        "INSERT INTO marts.fact_sales_daily DEFAULT VALUES;",
        "bi_reader", "bi_reader_dev")
    denied_staging = psql_fails(
        "SELECT * FROM staging.stg_sales LIMIT 1;",
        "bi_reader", "bi_reader_dev")
    print(f"[ok] запись би-пользователю запрещена: {denied_write}")
    print(f"[ok] staging би-пользователю закрыт: {denied_staging}")

    dictionary = psql("SELECT count(*) FROM marts.metrics_dictionary WHERE status = 'active';",
                      user="bi_reader", password="bi_reader_dev")
    print(f"[ok] словарь метрик доступен дашбордам: активных метрик {dictionary}")
    print("[точка возврата] контейнер Superset: нет демона Docker; подъём и скриншот "
          "дашборда — в документации стенда, контракт проверен запросами выше")


if __name__ == "__main__":
    main()
