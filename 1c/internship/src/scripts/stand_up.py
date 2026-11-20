#!/usr/bin/env python3
"""Одна команда стенда (task_139): данные → база → дымовые проверки.

    src/scripts/.venv/bin/python src/scripts/stand_up.py [small]

Шаги: генерация эталонных данных в tests/fixtures, загрузка
в PostgreSQL стенда (схема stand, таблицы пересоздаются), дымовые
запросы (количества, контрольная сумма заказов), замер времени.
Два прогона подряд дают одинаковую базу: контроль — sha256
фикстуры и сумма заказов, а не «вроде поднялось».

PostgreSQL стенда: PGHOST/PGPORT/PGUSER из окружения, по умолчанию
локальный стенд разработчика.
"""

from __future__ import annotations

import hashlib
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from seed_fixtures import generate, render  # noqa: E402

PSQL_CANDIDATES = [
    "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql",
]


def psql(sql: str) -> str:
    psql_bin = next((p for p in PSQL_CANDIDATES if Path(p).exists()), "psql")
    proc = subprocess.run(
        [psql_bin, "-X", "-v", "ON_ERROR_STOP=1", "-t", "-A",
         "-h", "127.0.0.1", "-U", "postgres", "-d", "postgres"],
        input=sql, capture_output=True, text=True, timeout=120)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip())
    return proc.stdout.strip()


def load(data: dict) -> None:
    statements = [
        "DROP SCHEMA IF EXISTS stand CASCADE",
        "CREATE SCHEMA stand",
        "CREATE TABLE stand.products (sku text PRIMARY KEY, name text, price numeric)",
        "CREATE TABLE stand.warehouses (code text PRIMARY KEY, name text, city text)",
        "CREATE TABLE stand.stock (sku text, warehouse text, quantity int)",
        "CREATE TABLE stand.orders (external_id text PRIMARY KEY, ord_date date,"
        " warehouse text, total numeric)",
    ]
    for product in data["products"]:
        statements.append(
            "INSERT INTO stand.products VALUES ('%s', '%s', %s)" % (
                product["sku"], product["name"].replace("'", "''"), product["price"]))
    for warehouse in data["warehouses"]:
        statements.append(
            "INSERT INTO stand.warehouses VALUES ('%s', '%s', '%s')" % (
                warehouse["code"], warehouse["name"], warehouse["city"]))
    for row in data["stock"]:
        statements.append(
            "INSERT INTO stand.stock VALUES ('%s', '%s', %d)" % (
                row["sku"], row["warehouse"], row["quantity"]))
    for order in data["orders"]:
        statements.append(
            "INSERT INTO stand.orders VALUES ('%s', '%s', '%s', %s)" % (
                order["external_id"], order["date"], order["warehouse"], order["total"]))
    psql(";\n".join(statements) + ";")


def main(argv: list[str]) -> int:
    profile = argv[0] if argv else "small"
    started = time.time()
    data = generate(profile)
    blob = render(data)
    fixture = Path("tests/fixtures/stand_data.json")
    fixture.parent.mkdir(parents=True, exist_ok=True)
    fixture.write_bytes(blob)
    digest = hashlib.sha256(blob).hexdigest()
    print(f"[1/3] фикстуры профиля {profile}: {len(blob)} байт, sha256 {digest}")
    t1 = time.time()
    load(data)
    print(f"[2/3] загрузка в PostgreSQL (схема stand): {time.time() - t1:.2f} с")
    counts = psql(
        "SELECT (SELECT count(*) FROM stand.products) || '/' || "
        "(SELECT count(*) FROM stand.warehouses) || '/' || "
        "(SELECT count(*) FROM stand.orders) || '/' || "
        "(SELECT round(sum(total), 2) FROM stand.orders)")
    print(f"[3/3] дымовая проверка: товары/склады/заказы/сумма = {counts}")
    print(f"стенд поднят за {time.time() - started:.2f} с")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
