#!/usr/bin/env python3
"""Проверки task_122: витрина продаж по дням на живой PostgreSQL.

Зеркало РИХ_Витрины: источник — выгрузка «Продаж» в staging, наполнение
полной перезаписью периода, сверка с источником до копейки, идемпотентный
пересчёт, правка задним числом без дублей, переименование товара (SCD-1),
замеры времени и объёма месяца.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_mart_sales.py
"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

PSQL_CANDIDATES = [
    os.environ.get("PSQL", ""),
    shutil.which("psql") or "",
    "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql",
]
PSQL = next((path for path in PSQL_CANDIDATES if path and Path(path).exists()), "")
CONN = ["-h", "/tmp/walk-pg", "-U", "rih", "-d", "rih", "-v", "ON_ERROR_STOP=1", "-q"]
ROOT = Path(__file__).resolve().parents[2]
PERIOD = ("2026-11-01", "2026-11-30")


def psql(sql: str = "", file: Path | None = None, timeout: int = 600) -> str:
    cmd = [PSQL, *CONN, "-t", "-A"]
    if file is not None:
        cmd += ["-f", str(file)]
    proc = subprocess.run(cmd, input=sql, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-600:])
    return proc.stdout.strip()


def load_period() -> tuple[float, int]:
    started = time.perf_counter()
    run_id = psql(f"""
        INSERT INTO marts.etl_runs (mart_name, period_from, period_to)
        VALUES ('fact_sales_daily', DATE '{PERIOD[0]}', DATE '{PERIOD[1]}')
        RETURNING run_id;""")
    loaded = psql(f"""
        DELETE FROM marts.fact_sales_daily
        WHERE date_key BETWEEN DATE '{PERIOD[0]}' AND DATE '{PERIOD[1]}';
        WITH inserted AS (
            INSERT INTO marts.fact_sales_daily
                (date_key, store_key, product_key, quantity, amount, cost, margin)
            SELECT s.sale_date, st.store_key, pr.product_key,
                   SUM(s.quantity), SUM(s.amount), SUM(s.cost),
                   SUM(s.amount) - SUM(s.cost)
            FROM staging.task122_turnover AS s
            JOIN marts.dim_store AS st ON st.store_code = s.store_code
            JOIN marts.dim_product AS pr ON pr.sku = s.sku
            WHERE s.sale_date BETWEEN DATE '{PERIOD[0]}' AND DATE '{PERIOD[1]}'
            GROUP BY s.sale_date, st.store_key, pr.product_key
            RETURNING 1
        )
        SELECT count(*) FROM inserted;""")
    psql(f"""
        UPDATE marts.etl_runs SET finished_at = now(), status = 'ok',
            rows_loaded = {loaded}
        WHERE run_id = {run_id};""")
    return time.perf_counter() - started, int(loaded)


def mart_totals() -> tuple[int, str, str]:
    out = psql(f"""
        SELECT count(*) || '|' || COALESCE(sum(amount),0) || '|' || COALESCE(sum(quantity),0)
        FROM marts.fact_sales_daily
        WHERE date_key BETWEEN DATE '{PERIOD[0]}' AND DATE '{PERIOD[1]}';""")
    rows, amount, qty = out.split("|")
    return int(rows), amount, qty


def main() -> None:
    assert PSQL, "psql не найден: задайте PSQL или поднимите стенд PostgreSQL"
    psql(file=ROOT / "tools/sql/marts/010_schema.sql")
    psql(file=ROOT / "tools/sql/marts/060_mart_sales_daily.sql")
    print("[ok] измерения стенда применены: dim_date/dim_store/dim_product + fact_sales_daily")

    psql("""
        DROP TABLE IF EXISTS staging.task122_turnover;
        CREATE TABLE staging.task122_turnover (
            sale_date DATE, store_code TEXT, sku TEXT,
            quantity NUMERIC(12,3), amount NUMERIC(14,2), cost NUMERIC(14,2));
        INSERT INTO staging.task122_turnover
        SELECT d::date, st.code, pr.sku,
               qty, ROUND(qty * pr.price, 2), ROUND(qty * pr.price * 0.7, 2)
        FROM generate_series(DATE '2026-11-01', DATE '2026-11-30', INTERVAL '1 day') AS d
        CROSS JOIN (VALUES ('MINSK-001'), ('MINSK-002'), ('BREST-001')) AS st(code)
        CROSS JOIN (VALUES ('SKU-00001', 3.20), ('SKU-00002', 2.10), ('SKU-00003', 5.40),
                          ('SKU-00004', 8.90), ('SKU-00005', 1.80)) AS pr(sku, price)
        CROSS JOIN LATERAL (
            SELECT CASE WHEN (EXTRACT(DAY FROM d)::int * 31 + length(st.code) + length(pr.sku)) % 13 = 0
                        THEN -1 * ((EXTRACT(DAY FROM d)::int + 3) % 4 + 1)
                        ELSE (EXTRACT(DAY FROM d)::int * 7 + pr.price::int * 3) % 11 END AS qty
        ) AS q;
    """)
    source = psql(f"""
        SELECT count(*) || '|' || sum(amount) FROM staging.task122_turnover
        WHERE sale_date BETWEEN DATE '{PERIOD[0]}' AND DATE '{PERIOD[1]}';""")
    print(f"[ok] источник месяца выгружен в staging: строк {source.split('|')[0]}, сумма {source.split('|')[1]}")

    elapsed, loaded = load_period()
    rows, amount, qty = mart_totals()
    assert (loaded, rows) == (450, 450), (loaded, rows)
    assert amount == source.split("|")[1], (amount, source)
    print(f"[ok] наполнение: {loaded} строк за {elapsed:.2f} с; сумма витрины = источнику {amount}")

    day_check = psql("""
        SELECT s.store_code || '=' || sum(f.amount)
        FROM marts.fact_sales_daily AS f
        JOIN marts.dim_store AS s ON s.store_key = f.store_key
        WHERE f.date_key = DATE '2026-11-15'
        GROUP BY s.store_code ORDER BY 1;""")
    source_day = psql("""
        SELECT store_code || '=' || sum(amount) FROM staging.task122_turnover
        WHERE sale_date = DATE '2026-11-15' GROUP BY store_code ORDER BY 1;""")
    assert day_check == source_day, (day_check, source_day)
    print(f"[ok] сверка дня по трём магазинам до копейки: {day_check.replace(chr(10), '; ')}")

    elapsed2, loaded2 = load_period()
    rows2, amount2, qty2 = mart_totals()
    assert (rows2, amount2, qty2) == (rows, amount, qty) and loaded2 == loaded
    print(f"[ok] повторный пересчёт месяца идемпотентен: строк {rows2}, суммы те же ({elapsed2:.2f} с)")

    psql("UPDATE staging.task122_turnover SET amount = amount + 100, quantity = quantity + 2 "
         "WHERE sale_date = DATE '2026-11-10' AND store_code = 'MINSK-001' AND sku = 'SKU-00001';")
    load_period()
    rows3, amount3, _ = mart_totals()
    assert rows3 == rows and float(amount3) == float(amount) + 100.0, (rows3, amount3)
    print(f"[ok] правка задним числом: строк по-прежнему {rows3}, сумма выросла ровно на 100.00")

    psql("UPDATE marts.dim_product SET product_name = 'Молоко 2,5% 1л (новое имя)' WHERE sku = 'SKU-00001';")
    name = psql("""
        SELECT product_name FROM marts.fact_sales_daily AS f
        JOIN marts.dim_product AS p ON p.product_key = f.product_key
        WHERE p.sku = 'SKU-00001' LIMIT 1;""")
    assert name.endswith("(новое имя)"), name
    print(f"[ok] переименование товара видно в витрине сразу (SCD-1): {name}")

    size = psql("SELECT pg_total_relation_size('marts.fact_sales_daily');")
    size_mb = int(size) / 1024 / 1024
    runs = psql("SELECT count(*) FROM marts.etl_runs WHERE mart_name = 'fact_sales_daily' AND status = 'ok';")
    print(f"[ok] объём витрины: строк {rows3}, размер {size_mb:.2f} МБ; успешных прогонов ETL: {runs}")

    psql(f"""
        DELETE FROM marts.fact_sales_daily WHERE date_key BETWEEN DATE '{PERIOD[0]}' AND DATE '{PERIOD[1]}';
        DELETE FROM marts.etl_runs WHERE mart_name = 'fact_sales_daily';
        DROP TABLE staging.task122_turnover;
        UPDATE marts.dim_product SET product_name = 'Молоко 2,5% 1л' WHERE sku = 'SKU-00001';
    """)
    print("[ok] тестовые данные витрины убраны, измерения стенда восстановлены")


if __name__ == "__main__":
    main()
