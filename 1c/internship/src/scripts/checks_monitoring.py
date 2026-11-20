#!/usr/bin/env python3
"""Проверки task_107: мониторинг — «что не обменено» находит пропуск.

Объект изменён после метки, но в отправленных сообщениях его нет:
отчёт обязан показать именно его; после отправки отчёт пуст.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_monitoring.py
"""

from __future__ import annotations

import os
import subprocess

PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
ENV = dict(os.environ, PGPASSWORD="rih_local_dev_only")


def sql(query: str) -> str:
    result = subprocess.run(
        [PSQL, "-h", "/tmp/walk-pg", "-p", "5432", "-U", "rih", "-d", "rih",
         "-v", "ON_ERROR_STOP=1", "-tAc", query],
        capture_output=True, text=True, env=ENV)
    if result.returncode != 0:
        raise RuntimeError(result.stderr)
    return result.stdout.strip()


def not_exchanged() -> str:
    return sql("""SELECT p.sku FROM mon.products p
                  WHERE p.changed_at > (SELECT mark FROM mon.watermark)
                    AND NOT EXISTS (SELECT 1 FROM mon.sent s WHERE s.sku = p.sku)
                  ORDER BY p.sku""")


def main() -> None:
    sql("DROP SCHEMA IF EXISTS mon CASCADE")
    sql("""CREATE SCHEMA mon;
           CREATE TABLE mon.products(sku text PRIMARY KEY, changed_at timestamptz);
           CREATE TABLE mon.sent(sku text, sent_at timestamptz);
           CREATE TABLE mon.watermark(mark timestamptz);
           INSERT INTO mon.watermark VALUES (now() - interval '1 hour');
           INSERT INTO mon.products VALUES ('SKU-OLD', now() - interval '2 hours'),
                                           ('SKU-SENT', now()), ('SKU-MISSED', now());
           INSERT INTO mon.sent VALUES ('SKU-SENT', now())""")

    missed = not_exchanged()
    assert missed == "SKU-MISSED", missed
    print(f"[ok] «что не обменено» нашло именно пропуск: {missed}")

    sql("INSERT INTO mon.sent VALUES ('SKU-MISSED', now())")
    assert not_exchanged() == ""
    print("[ok] после отправки отчёт пуст: пропуск закрыт, а не спрятан")


if __name__ == "__main__":
    main()
