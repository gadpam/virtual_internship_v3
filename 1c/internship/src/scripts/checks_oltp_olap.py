#!/usr/bin/env python3
"""Проверки task_121: цена отчёта по оперативной базе (эксперимент).

На живой PostgreSQL стенда: 50 «проведений» (транзакция: документ +
100 движений и обновлений остатков) меряются сначала на тихой базе,
затем под тремя аналитическими сессиями по 1.2 млн строк истории.
Деградация — цифрами, на непустой базе.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_oltp_olap.py
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
POSTINGS = 50
HISTORY_ROWS = 1_200_000


def psql(sql: str, timeout: int = 600) -> str:
    proc = subprocess.run([PSQL, *CONN, "-t", "-A"],
                          input=sql, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-500:])
    return proc.stdout.strip()


def setup() -> None:
    psql("DROP SCHEMA IF EXISTS task121 CASCADE; CREATE SCHEMA task121;")
    psql(f"""
        CREATE TABLE task121.sales_history (
            id BIGSERIAL PRIMARY KEY, doc_date DATE NOT NULL,
            shop INT NOT NULL, product INT NOT NULL,
            qty NUMERIC(12,3) NOT NULL, amount NUMERIC(14,2) NOT NULL);
        INSERT INTO task121.sales_history (doc_date, shop, product, qty, amount)
        SELECT DATE '2026-01-01' + (g % 300), 1 + (g % 40), 1 + (g % 5000),
               1 + (g % 5), 10 + (g % 900)
        FROM generate_series(1, {HISTORY_ROWS}) AS g;
        CREATE TABLE task121.stock (shop INT, product INT, qty NUMERIC(12,3),
                                    PRIMARY KEY (shop, product));
        INSERT INTO task121.stock SELECT 1 + (g % 40), 1 + (g % 5000), 1000
        FROM generate_series(1, 200000) AS g ON CONFLICT DO NOTHING;
        CREATE TABLE task121.docs (id BIGSERIAL PRIMARY KEY,
                                   posted_at TIMESTAMPTZ DEFAULT now(), total NUMERIC(14,2));
        CREATE TABLE task121.movements (doc_no INT, shop INT, product INT, qty NUMERIC(12,3));
        CREATE INDEX ix_task121_mov ON task121.movements (shop, product);
    """)


def run_postings(offset: int = 0) -> float:
    lines = []
    for number in range(1, POSTINGS + 1):
        doc_no = offset + number
        values = ", ".join(
            f"({1 + ((doc_no + line) % 40)}, {1 + ((doc_no * 7 + line) % 5000)}, 1)"
            for line in range(100))
        lines.append(
            "BEGIN; "
            f"INSERT INTO task121.docs (total) VALUES ({100 + number}); "
            f"INSERT INTO task121.movements (doc_no, shop, product, qty) "
            f"SELECT {doc_no}, shop, product, qty FROM (VALUES {values}) AS v(shop, product, qty); "
            f"UPDATE task121.stock AS s SET qty = s.qty - 1 FROM (VALUES {values}) AS v(shop, product, qty) "
            "WHERE s.shop = v.shop AND s.product = v.product; "
            "COMMIT;")
    started = time.perf_counter()
    psql("\n".join(lines))
    return time.perf_counter() - started


def heavy_query_process() -> subprocess.Popen:
    sql = ("SELECT shop, date_trunc('month', doc_date), sum(amount), sum(qty) "
           "FROM task121.sales_history GROUP BY 1, 2 ORDER BY 1, 2;")
    repeated = " ".join([sql] * 40)
    return subprocess.Popen([PSQL, *CONN, "-c", repeated],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> None:
    assert PSQL, "psql не найден: задайте PSQL или поднимите стенд PostgreSQL"
    setup()
    rows = psql("SELECT count(*) FROM task121.sales_history;")
    print(f"[ok] оперативная история на стенде: строк {rows} (не пустая база)")

    baseline = run_postings()
    print(f"[ok] проведение {POSTINGS} документов без фона: {baseline:.2f} с "
          f"({baseline / POSTINGS * 1000:.0f} мс/документ)")

    heavy = [heavy_query_process() for _ in range(3)]
    time.sleep(0.5)
    try:
        under_load = run_postings(offset=1000)
    finally:
        for proc in heavy:
            proc.terminate()
        for proc in heavy:
            proc.wait(timeout=30)
    print(f"[ok] те же {POSTINGS} документов под аналитическим запросом: {under_load:.2f} с "
          f"({under_load / POSTINGS * 1000:.0f} мс/документ)")

    ratio = under_load / baseline if baseline else 0
    print(f"[ok] деградация проведения: ×{ratio:.1f} — отчёт директора платит касса")
    assert ratio > 1.5, f"деградация не показана: ×{ratio:.2f}"

    docs = psql("SELECT count(*) FROM task121.docs;")
    movements = psql("SELECT count(*) FROM task121.movements;")
    assert docs == str(POSTINGS * 2) and movements == str(POSTINGS * 2 * 100), (docs, movements)
    psql("DROP SCHEMA task121 CASCADE;")
    print(f"[ok] все {docs} проведений и {movements} движений зафиксированы, схема убрана")


if __name__ == "__main__":
    main()
