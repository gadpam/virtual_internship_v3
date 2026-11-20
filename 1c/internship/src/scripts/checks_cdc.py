#!/usr/bin/env python3
"""Проверки task_123: CDC для витрины — дельта, заднее число, удаления.

На живой PostgreSQL: источник продаж, журнал изменений (аналог подписки
на запись/удаление в 1С), потребитель-витрина применяет дельту
пересчётом затронутых дней. Полная выгрузка и дельта замерены на объёме.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_cdc.py
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


def psql(sql: str, timeout: int = 600) -> str:
    proc = subprocess.run([PSQL, *CONN, "-t", "-A"], input=sql,
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-600:])
    return proc.stdout.strip()


def setup() -> None:
    psql("""
        DROP SCHEMA IF EXISTS task123 CASCADE; CREATE SCHEMA task123;
        CREATE TABLE task123.src_sales (
            id BIGINT PRIMARY KEY, sale_date DATE NOT NULL,
            store INT NOT NULL, sku INT NOT NULL,
            qty NUMERIC(12,3) NOT NULL, amount NUMERIC(14,2) NOT NULL);
        INSERT INTO task123.src_sales
        SELECT g, DATE '2026-03-01' + (g % 92), 1 + (g % 3), 1 + (g % 50),
               1 + (g % 5), 10 + (g % 400)
        FROM generate_series(1, 100000) AS g;
        CREATE TABLE task123.cdc_journal (
            seq BIGSERIAL PRIMARY KEY, object_id BIGINT NOT NULL,
            op CHAR(1) NOT NULL, sale_date DATE NOT NULL,
            changed_at TIMESTAMPTZ NOT NULL DEFAULT now());
        CREATE TABLE task123.mart (
            sale_date DATE, store INT, sku INT,
            qty NUMERIC(14,3), amount NUMERIC(16,2),
            PRIMARY KEY (sale_date, store, sku));
        CREATE TABLE task123.consumer_state (applied_seq BIGINT NOT NULL);
        INSERT INTO task123.consumer_state VALUES (0);
    """)


def full_load() -> tuple[float, int]:
    started = time.perf_counter()
    out = psql("""
        DELETE FROM task123.mart;
        WITH inserted AS (
            INSERT INTO task123.mart
            SELECT sale_date, store, sku, sum(qty), sum(amount)
            FROM task123.src_sales GROUP BY 1, 2, 3
            RETURNING 1)
        SELECT count(*) FROM inserted;""")
    return time.perf_counter() - started, int(out)


def change_update(object_id: int, add_amount: int) -> None:
    # Имитация подписки 1С: изменение и запись журнала — одна транзакция,
    # дата дня берётся из самой строки, а не называется вызывающим.
    psql(f"""
        UPDATE task123.src_sales SET amount = amount + {add_amount} WHERE id = {object_id};
        INSERT INTO task123.cdc_journal (object_id, op, sale_date)
        SELECT id, 'U', sale_date FROM task123.src_sales WHERE id = {object_id};""")


def change_delete(object_id: int) -> None:
    # Подписка «перед удалением»: tombstone пишется до физического удаления.
    psql(f"""
        INSERT INTO task123.cdc_journal (object_id, op, sale_date)
        SELECT id, 'D', sale_date FROM task123.src_sales WHERE id = {object_id};
        DELETE FROM task123.src_sales WHERE id = {object_id};""")


def apply_delta() -> int:
    applied_seq = int(psql("SELECT applied_seq FROM task123.consumer_state;"))
    pending = psql(f"""
        SELECT count(*) || '|' || COALESCE(string_agg(DISTINCT sale_date::text, ','), '')
        FROM task123.cdc_journal WHERE seq > {applied_seq};""")
    count_s, dates_s = pending.split("|")
    if int(count_s) == 0:
        return 0
    dates = ",".join(f"DATE '{day}'" for day in dates_s.split(","))
    psql(f"DELETE FROM task123.mart WHERE sale_date IN ({dates});")
    psql(f"""
        INSERT INTO task123.mart
        SELECT sale_date, store, sku, sum(qty), sum(amount)
        FROM task123.src_sales WHERE sale_date IN ({dates})
        GROUP BY 1, 2, 3;""")
    psql("UPDATE task123.consumer_state "
         "SET applied_seq = (SELECT COALESCE(max(seq), 0) FROM task123.cdc_journal);")
    return int(count_s)


def delta_size(since_seq: int) -> tuple[int, int]:
    out = psql(f"""
        SELECT count(*) || '|' || COALESCE(sum(octet_length(row_to_json(j)::text)), 0)
        FROM task123.cdc_journal AS j WHERE seq > {since_seq};""")
    count, size = out.split("|")
    return int(count), int(size)


def totals(table: str) -> str:
    return psql(f"SELECT count(*) || '|' || sum(amount) FROM task123.{table};")


def main() -> None:
    assert PSQL, "psql не найден: задайте PSQL или поднимите стенд PostgreSQL"
    setup()
    full_time, mart_rows = full_load()
    src_total = totals("src_sales")
    assert totals("mart").split("|")[1] == src_total.split("|")[1]
    full_bytes = psql("SELECT sum(octet_length(row_to_json(s)::text)) FROM task123.src_sales AS s;")
    print(f"[ok] полная начальная выгрузка: источник {src_total.split('|')[0]} строк, "
          f"витрина {mart_rows} строк зерна за {full_time:.2f} с, JSON источника {int(full_bytes)/1e6:.1f} МБ")

    current_seq = int(psql("SELECT COALESCE(max(seq),0) FROM task123.cdc_journal;"))
    started = time.perf_counter()
    for number in range(1, 3001):
        change_update(number, 1)
    change_time = time.perf_counter() - started
    count, size = delta_size(current_seq)
    assert count == 3000, count
    print(f"[ok] сутки изменений: {count} записей дельты ({size/1024:.0f} КБ JSON) "
          f"против полной {int(full_bytes)/1e6:.1f} МБ — в {int(full_bytes)//max(size,1)} раз меньше")

    applied = apply_delta()
    assert applied == 3000, applied
    mart_total = totals("mart").split("|")[1]
    assert mart_total == totals("src_sales").split("|")[1], (mart_total, totals("src_sales"))
    again = apply_delta()
    assert again == 0
    print("[ok] дельта применена пересчётом затронутых дней, витрина сошлась с источником; "
          "повторная дельта пуста — неизменённое не отдаётся дважды")

    march_day = psql("SELECT sale_date FROM task123.src_sales WHERE id = 4242;")
    march_before = psql(f"SELECT sum(amount) FROM task123.mart WHERE sale_date = DATE '{march_day}';")
    change_update(4242, 500)
    applied = apply_delta()
    march_after = psql(f"SELECT sum(amount) FROM task123.mart WHERE sale_date = DATE '{march_day}';")
    src_march = psql(f"SELECT sum(amount) FROM task123.src_sales WHERE sale_date = DATE '{march_day}';")
    assert march_after == src_march and float(march_after) == float(march_before) + 500.0
    print(f"[ok] заднее число: мартовский день изменён в апреле, дельта подхватила: "
          f"{march_before} -> {march_after}, сверка сошлась")

    victim = psql("SELECT id FROM task123.src_sales WHERE sale_date = DATE '2026-03-12' LIMIT 1;")
    change_delete(int(victim))
    apply_delta()
    day_after = psql("SELECT sum(amount) FROM task123.mart WHERE sale_date = DATE '2026-03-12';")
    src_day = psql("SELECT sum(amount) FROM task123.src_sales WHERE sale_date = DATE '2026-03-12';")
    assert day_after == src_day
    print(f"[ok] физическое удаление: tombstone в журнале, витрина пересчитала день, "
          f"призрака не осталось (день {src_day})")

    old_seq = int(psql("SELECT applied_seq FROM task123.consumer_state;"))
    for number in range(5001, 5501):
        change_update(number, 2)
    applied = apply_delta()
    assert applied == 500
    print(f"[ok] простой потребителя: дельта со старого seq {old_seq} догнала все {applied} изменений, день не потерян")

    final_src = totals("src_sales").split("|")[1]
    final_mart = totals("mart").split("|")[1]
    assert final_src == final_mart
    psql("DROP SCHEMA task123 CASCADE;")
    print(f"[ok] итоговая сверка витрины с источником: {final_mart} = {final_src}; схема убрана")


if __name__ == "__main__":
    main()
