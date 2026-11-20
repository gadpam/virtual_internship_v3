#!/usr/bin/env python3
"""Проверки task_124: три способа выгрузки на 1 млн строк (зеркало).

Файл CSV+gzip с манифестом и проверкой получателем, таблица СУБД
транзакцией, HTTP-поток курсорными страницами с дозабором после
обрыва. Замеры: время, размер, пик памяти клиента.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_export_methods.py
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
import tracemalloc
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

PSQL_CANDIDATES = [
    os.environ.get("PSQL", ""),
    shutil.which("psql") or "",
    "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql",
]
PSQL = next((path for path in PSQL_CANDIDATES if path and Path(path).exists()), "")
CONN = ["-h", "/tmp/walk-pg", "-U", "rih", "-d", "rih", "-v", "ON_ERROR_STOP=1", "-q"]
ROWS = 1_000_000
WORK = Path("/tmp/task124")
FORMAT_VERSION = "sales-export/1"


def psql(sql: str, timeout: int = 900) -> str:
    proc = subprocess.run([PSQL, *CONN, "-t", "-A"], input=sql,
                          capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-600:])
    return proc.stdout.strip()


def setup() -> None:
    psql(f"""
        DROP SCHEMA IF EXISTS task124 CASCADE; CREATE SCHEMA task124;
        CREATE TABLE task124.src (
            id BIGINT PRIMARY KEY, sale_date DATE NOT NULL,
            store INT NOT NULL, sku INT NOT NULL,
            qty NUMERIC(12,3) NOT NULL, amount NUMERIC(14,2) NOT NULL);
        INSERT INTO task124.src
        SELECT g, DATE '2026-11-01' + (g % 30), 1 + (g % 3), 1 + (g % 50),
               1 + (g % 5), 10 + (g % 400)
        FROM generate_series(1, {ROWS}) AS g;
        CREATE TABLE task124.target (LIKE task124.src INCLUDING ALL);
    """)


def export_file() -> dict:
    csv_path = WORK / "sales.csv"
    started = time.perf_counter()
    proc = subprocess.run(
        [PSQL, *CONN, "-c",
         f"\\copy (SELECT id, sale_date, store, sku, qty, amount FROM task124.src ORDER BY id) "
         f"TO '{csv_path}' WITH (FORMAT csv, HEADER true)"],
        capture_output=True, text=True, timeout=900)
    assert proc.returncode == 0, proc.stderr[-400:]
    raw = csv_path.read_bytes()
    packed = gzip.compress(raw, compresslevel=6)
    (WORK / "sales.csv.gz").write_bytes(packed)
    manifest = {"format": FORMAT_VERSION, "rows": ROWS,
                "sha256": hashlib.sha256(packed).hexdigest(),
                "amount_sum": psql("SELECT sum(amount) FROM task124.src;")}
    (WORK / "sales.ctl.json").write_text(json.dumps(manifest), encoding="utf-8")
    return {"seconds": time.perf_counter() - started, "csv_mb": len(raw) / 1e6,
            "gz_mb": len(packed) / 1e6, "manifest": manifest}


def verify_received(gz_bytes: bytes, manifest: dict) -> tuple[bool, str]:
    if manifest.get("format") != FORMAT_VERSION:
        return False, f"неизвестная версия формата: {manifest.get('format')}"
    if hashlib.sha256(gz_bytes).hexdigest() != manifest["sha256"]:
        return False, "контрольная сумма не сошлась: файл обрезан или повреждён"
    try:
        text = gzip.decompress(gz_bytes).decode("utf-8")
    except Exception as err:
        return False, f"gzip не читается: {err}"
    lines = text.count("\n") - 1
    if lines != manifest["rows"]:
        return False, f"строк {lines} против манифеста {manifest['rows']}"
    return True, "принято"


def export_db() -> float:
    started = time.perf_counter()
    psql("BEGIN; INSERT INTO task124.target SELECT * FROM task124.src; COMMIT;")
    return time.perf_counter() - started


class ExportHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802 - имя из http.server
        params = parse_qs(urlparse(self.path).query)
        cursor = int(params.get("cursor", ["0"])[0])
        limit = min(int(params.get("limit", ["5000"])[0]), 20000)
        out = psql(f"""
            SELECT id || '|' || sale_date || '|' || store || '|' || sku || '|' || qty || '|' || amount
            FROM task124.src WHERE id > {cursor} ORDER BY id LIMIT {limit};""")
        rows = [line.split("|") for line in out.splitlines() if line]
        payload = json.dumps({
            "rows": [{"id": int(r[0]), "amount": r[5]} for r in rows],
            "next_cursor": int(rows[-1][0]) if rows else cursor,
        }).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args) -> None:
        pass


def fetch_page(port: int, cursor: int, limit: int = 5000) -> dict:
    with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/export?cursor={cursor}&limit={limit}", timeout=60) as resp:
        return json.loads(resp.read().decode())


def export_http(port: int) -> dict:
    tracemalloc.start()
    started = time.perf_counter()
    cursor, total, amount_sum = 0, 0, 0.0
    while True:
        page = fetch_page(port, cursor)
        if not page["rows"]:
            break
        total += len(page["rows"])
        amount_sum += sum(float(r["amount"]) for r in page["rows"])
        cursor = page["next_cursor"]
    seconds = time.perf_counter() - started
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {"seconds": seconds, "rows": total, "amount_sum": amount_sum,
            "peak_mb": peak / 1e6, "cursor": cursor}


def main() -> None:
    assert PSQL, "psql не найден: задайте PSQL или поднимите стенд PostgreSQL"
    WORK.mkdir(exist_ok=True)
    setup()
    print(f"[ok] источник выгрузки на стенде: {ROWS} строк")

    file_result = export_file()
    gz_bytes = (WORK / "sales.csv.gz").read_bytes()
    ok, message = verify_received(gz_bytes, file_result["manifest"])
    assert ok, message
    bad_ok, bad_message = verify_received(gz_bytes[: len(gz_bytes) // 2], file_result["manifest"])
    version_ok, version_message = verify_received(
        gz_bytes, {**file_result["manifest"], "format": "sales-export/99"})
    assert not bad_ok and not version_ok
    print(f"[ok] файл: CSV {file_result['csv_mb']:.1f} МБ -> gzip {file_result['gz_mb']:.1f} МБ "
          f"за {file_result['seconds']:.2f} с; получатель принял по манифесту")
    print(f"[ok] обрезанный файл отклонён («{bad_message}»), чужая версия — тоже («{version_message}»)")

    db_seconds = export_db()
    target_rows = psql("SELECT count(*) FROM task124.target;")
    psql("CREATE TABLE task124.partial (LIKE task124.src); "
         "BEGIN; INSERT INTO task124.partial SELECT * FROM task124.src LIMIT 100000; ROLLBACK;")
    after_rollback = psql("SELECT count(*) FROM task124.partial;")
    assert target_rows == str(ROWS) and after_rollback == "0"
    print(f"[ok] таблица СУБД: {target_rows} строк за {db_seconds:.2f} с одной транзакцией; "
          f"обрыв посередине = откат, частично записанных строк нет")

    server = ThreadingHTTPServer(("127.0.0.1", 0), ExportHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        first = fetch_page(port, 0)
        cursor = first["next_cursor"]
        taken = len(first["rows"])
        resumed_total, resumed_sum = taken, sum(float(r["amount"]) for r in first["rows"])
        while True:
            page = fetch_page(port, cursor)
            if not page["rows"]:
                break
            resumed_total += len(page["rows"])
            resumed_sum += sum(float(r["amount"]) for r in page["rows"])
            cursor = page["next_cursor"]
        assert resumed_total == ROWS, resumed_total
        print(f"[ok] HTTP: обрыв после {taken} строк, дозабор с курсора {first['next_cursor']} "
              f"довёл до {resumed_total} без повторов и «сначала»")

        http = export_http(port)
        src_sum = float(psql("SELECT sum(amount) FROM task124.src;"))
        assert http["rows"] == ROWS and abs(http["amount_sum"] - src_sum) < 0.01
        print(f"[ok] HTTP-поток целиком: {http['rows']} строк за {http['seconds']:.2f} с, "
              f"пик памяти клиента {http['peak_mb']:.1f} МБ, сумма сошлась")
    finally:
        server.shutdown()

    print(f"[ok] ЗАМЕРЫ 1 млн строк: файл {file_result['seconds']:.2f} с "
          f"(gzip {file_result['gz_mb']:.1f} МБ) | таблица СУБД {db_seconds:.2f} с | "
          f"HTTP курсором {http['seconds']:.2f} с")
    psql("DROP SCHEMA task124 CASCADE;")
    print("[ok] схема эксперимента убрана")


if __name__ == "__main__":
    main()
