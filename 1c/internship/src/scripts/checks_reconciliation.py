#!/usr/bin/env python3
"""Проверки task_125: словарь метрик в деле — автосверка витрины (зеркало).

На живой PostgreSQL: источник и витрина сверяются по дням; расхождения
классифицируются — свежесть (дельта не применена), задним числом
(закрытый период правили), правила (формулы разошлись). Уведомление
владельцу метрики уходит только выше порога 0.5% за период.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_reconciliation.py
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
CONN = ["-h", "/tmp/walk-pg", "-U", "rih", "-d", "rih", "-v", "ON_ERROR_STOP=1", "-q"]
THRESHOLD_PCT = 0.5
TODAY = "2026-12-05"
CLOSED_BEFORE = "2026-12-01"


def psql(sql: str, timeout: int = 600) -> str:
    proc = subprocess.run([PSQL, *CONN, "-t", "-A"], input=sql,
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-600:])
    return proc.stdout.strip()


def setup() -> None:
    psql(f"""
        DROP SCHEMA IF EXISTS task125 CASCADE; CREATE SCHEMA task125;
        CREATE TABLE task125.src (
            id BIGSERIAL PRIMARY KEY, sale_date DATE NOT NULL,
            store INT NOT NULL, amount NUMERIC(14,2) NOT NULL);
        INSERT INTO task125.src (sale_date, store, amount)
        SELECT DATE '2026-11-01' + (g % 30), 1 + (g % 3), 1000 + (g % 500)
        FROM generate_series(1, 900) AS g;
        INSERT INTO task125.src (sale_date, store, amount)
        SELECT DATE '2026-12-01' + (g % 4), 1 + (g % 3), 1000 + (g % 500)
        FROM generate_series(1, 60) AS g;
        CREATE TABLE task125.mart (
            sale_date DATE, store INT, amount NUMERIC(16,2),
            loaded_at DATE, PRIMARY KEY (sale_date, store));
        CREATE TABLE task125.journal (
            seq BIGSERIAL PRIMARY KEY, sale_date DATE NOT NULL,
            changed_on DATE NOT NULL, processed BOOLEAN NOT NULL DEFAULT FALSE);
        CREATE TABLE task125.notifications (
            metric TEXT, diff_pct NUMERIC(8,2), note TEXT);
        INSERT INTO task125.mart
        SELECT sale_date, store, sum(amount), DATE '2026-12-04'
        FROM task125.src GROUP BY 1, 2;
    """)


def reconcile() -> list[dict]:
    out = psql("""
        SELECT COALESCE(s.sale_date, m.sale_date) || '|' ||
               COALESCE(s.store, m.store) || '|' ||
               COALESCE(s.amount, 0) || '|' || COALESCE(m.amount, 0)
        FROM (SELECT sale_date, store, sum(amount) AS amount
              FROM task125.src GROUP BY 1, 2) AS s
        FULL JOIN task125.mart AS m
          ON m.sale_date = s.sale_date AND m.store = s.store
        WHERE COALESCE(s.amount, 0) <> COALESCE(m.amount, 0)
        ORDER BY 1;""")
    result = []
    for line in out.splitlines():
        if not line:
            continue
        day, store, src, mart = line.split("|")
        diff = float(src) - float(mart)
        pct = 100.0 if float(src) == 0 else round(100 * diff / float(src), 2)
        result.append({"day": day, "store": int(store), "src": float(src),
                       "mart": float(mart), "diff": diff, "pct": pct,
                       "kind": classify(day, int(store))})
    return result


def classify(day: str, store: int) -> str:
    pending = psql(f"""
        SELECT count(*) FROM task125.journal
        WHERE sale_date = DATE '{day}' AND NOT processed;""")
    backdated = psql(f"""
        SELECT count(*) FROM task125.journal AS j
        JOIN task125.mart AS m ON m.sale_date = j.sale_date AND m.store = {store}
        WHERE j.sale_date = DATE '{day}' AND j.sale_date < DATE '{CLOSED_BEFORE}'
          AND j.changed_on > m.loaded_at;""")
    if day < CLOSED_BEFORE and int(backdated) > 0:
        return "задним числом"
    if int(pending) > 0:
        return "свежесть"
    return "правила"


def notify_if_needed(diffs: list[dict]) -> bool:
    totals = psql("SELECT sum(amount) FROM task125.src;")
    diff_sum = sum(item["diff"] for item in diffs)
    pct = round(100 * diff_sum / float(totals), 2) if float(totals) else 0.0
    if diffs and abs(pct) > THRESHOLD_PCT:
        psql(f"INSERT INTO task125.notifications VALUES "
             f"('M-001 Выручка', {pct}, 'расхождение выше порога, владелец: финансы');")
        return True
    return False


def change_source(day: str, store: int, delta: float, processed: bool = False) -> None:
    psql(f"""
        UPDATE task125.src SET amount = amount + {delta}
        WHERE id = (SELECT id FROM task125.src
                    WHERE sale_date = DATE '{day}' AND store = {store} LIMIT 1);
        INSERT INTO task125.journal (sale_date, changed_on, processed)
        VALUES (DATE '{day}', DATE '{TODAY}', {str(processed).lower()});""")


def reload_day(day: str) -> None:
    psql(f"""
        DELETE FROM task125.mart WHERE sale_date = DATE '{day}';
        INSERT INTO task125.mart
        SELECT sale_date, store, sum(amount), DATE '{TODAY}'
        FROM task125.src WHERE sale_date = DATE '{day}' GROUP BY 1, 2;
        UPDATE task125.journal SET processed = TRUE WHERE sale_date = DATE '{day}';""")


def main() -> None:
    assert PSQL, "psql не найден: задайте PSQL или поднимите стенд PostgreSQL"
    setup()
    assert reconcile() == []
    print("[ok] исходная сверка: витрина сходится с источником по всем дням")

    change_source("2026-12-03", 1, 30.0)
    diffs = reconcile()
    assert len(diffs) == 1 and diffs[0]["kind"] == "свежесть", diffs
    assert not notify_if_needed(diffs)
    print(f"[ok] класс «свежесть»: правка дня 2026-12-03 без пересчёта — {diffs[0]}, "
          f"расхождение периода ниже порога {THRESHOLD_PCT}% — тишина, а не вой")
    reload_day("2026-12-03")
    assert reconcile() == []

    closed_store = int(psql("SELECT store FROM task125.src WHERE sale_date = DATE '2026-11-10' LIMIT 1;"))
    change_source("2026-11-10", closed_store, 9000.0)
    diffs = reconcile()
    assert len(diffs) == 1 and diffs[0]["kind"] == "задним числом", diffs
    assert notify_if_needed(diffs)
    note = psql("SELECT metric || ': ' || diff_pct || '%' FROM task125.notifications;")
    print(f"[ok] намеренное расхождение задним числом найдено: {diffs[0]}")
    print(f"[ok] уведомление владельцу метрики ушло выше порога: {note}")
    reload_day("2026-11-10")
    assert reconcile() == []
    print("[ok] после пересчёта затронутого дня сверка снова чиста")

    psql("UPDATE task125.mart SET amount = amount + 777 WHERE sale_date = DATE '2026-12-02' AND store = 3;")
    diffs = reconcile()
    assert len(diffs) == 1 and diffs[0]["kind"] == "правила", diffs
    print(f"[ok] класс «правила»: витрину поправили мимо источника и журнала — {diffs[0]}")
    psql("DROP SCHEMA task125 CASCADE;")
    print("[ok] схема эксперимента убрана")


if __name__ == "__main__":
    main()
