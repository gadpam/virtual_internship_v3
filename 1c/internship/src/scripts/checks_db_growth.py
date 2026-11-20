#!/usr/bin/env python3
"""Проверки task_185: рост данных, WAL и временных таблиц в PostgreSQL.

Аналоги MS SQL на стенде: журнал транзакций — WAL (pg_wal_lsn_diff),
tempdb — временные таблицы и temp files сортировок (pg_stat_database).
Массовая загрузка измеряется цифрами до/после, а не «база выросла».

Запуск: src/scripts/.venv/bin/python src/scripts/checks_db_growth.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    out = psql("""
DROP SCHEMA IF EXISTS growth CASCADE;
CREATE SCHEMA growth;
CREATE TABLE growth.movements (id int, sku text, qty numeric);
SELECT 'before|' || pg_database_size(current_database()) || '|' ||
       pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')::bigint || '|' ||
       temp_files || '|' || temp_bytes
FROM pg_stat_database WHERE datname = current_database();
INSERT INTO growth.movements
SELECT g, 'SKU-' || (g % 1000), (g % 97) + 1 FROM generate_series(1, 300000) g;
SELECT 'after|' || pg_database_size(current_database()) || '|' ||
       pg_wal_lsn_diff(pg_current_wal_lsn(), '0/0')::bigint || '|' ||
       temp_files || '|' || temp_bytes || '|' ||
       (SELECT count(*) FROM growth.movements)
FROM pg_stat_database WHERE datname = current_database();
SET work_mem = '64kB';
CREATE TEMP TABLE tmp_growth_sort AS
SELECT g, md5(g::text) AS digest FROM generate_series(1, 200000) g;
SELECT 'temp|' || pg_total_relation_size('tmp_growth_sort') || '|' ||
       count(*) FROM tmp_growth_sort;
SELECT 'sorted|' || count(*) FROM
    (SELECT digest FROM tmp_growth_sort ORDER BY digest) ordered;
""")
    metrics = {}
    for line in out.splitlines():
        parts = line.split("|")
        if parts and parts[0] in ("before", "after", "temp", "sorted"):
            metrics[parts[0]] = [int(x) for x in parts[1:]]
    assert len(metrics) == 4, out
    before, after, temp = metrics["before"], metrics["after"], metrics["temp"]
    assert after[4] == 300_000 and temp[1] == 200_000 and metrics["sorted"][0] == 200_000
    assert after[1] > before[1] and after[0] >= before[0]
    assert temp[0] > 1_000_000
    temp_stats = psql(
        "SELECT temp_files || '|' || temp_bytes FROM pg_stat_database "
        "WHERE datname = current_database()")
    temp_files, temp_bytes = (int(x) for x in temp_stats.split("|"))
    assert temp_bytes >= before[3]
    print(f"[ok] массовая загрузка 300 000 строк: WAL +{after[1] - before[1]} байт, "
          f"размер базы {before[0]} -> {after[0]} байт — рост измерен, а не угадан")
    print(f"[ok] временная таблица: {temp[0]} байт; сортировка 200 000 строк при work_mem=64kB "
          f"выполнена; temp files базы {before[2]} -> {temp_files}, temp bytes {before[3]} -> {temp_bytes}")
    print("[ok] вывод для эксплуатации: длинная транзакция удерживает WAL от "
          "переиспользования, массовые операции раздувают и журнал, и temp-область")


if __name__ == "__main__":
    main()
