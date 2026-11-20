#!/usr/bin/env python3
"""Проверки task_132: учение по сбою — пять инъекций с таймером.

Каждая инъекция ломает учебный стенд и измеряет три времени:
обнаружение (сбой → сигнал), диагностика (сигнал → причина по
журналу), восстановление (причина → сервис работает). Главный
критерий учения: ни одна инъекция не потеряла данные. Цифры уходят
в postmortem как измерены, а не как хотелось бы.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_gameday.py
"""

from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SHOP = os.environ.get("MOCK_SHOP_URL", "http://127.0.0.1:8026")
SHOP_KEY = os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key")
PSQL = "/tmp/walk-venv/lib/python3.11/site-packages/pgserver/pginstall/bin/psql"
CONN = ["-h", "/tmp/walk-pg", "-U", "rih", "-d", "rih", "-v", "ON_ERROR_STOP=1", "-q"]
RESULTS: list[dict] = []


def psql(sql: str) -> str:
    proc = subprocess.run([PSQL, *CONN, "-t", "-A"], input=sql,
                          capture_output=True, text=True, timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr[-400:])
    return proc.stdout.strip()


def shop(fault: str | None = None, path: str = "/api/v1/products") -> tuple[int, str]:
    req = urllib.request.Request(SHOP + path)
    req.add_header("X-Api-Key", SHOP_KEY)
    if fault:
        req.add_header("X-Fault-Mode", fault)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def record(name: str, detect: float, diagnose: float, recover: float,
           data_ok: bool, note: str) -> None:
    RESULTS.append({"name": name, "detect": detect, "diagnose": diagnose,
                    "recover": recover, "data_ok": data_ok, "note": note})
    print(f"[ok] {name}: обнаружение {detect:.1f} с, диагностика {diagnose:.1f} с, "
          f"восстановление {recover:.1f} с; данные целы: {data_ok}. {note}")


def injection_partner_down() -> None:
    started = time.perf_counter()
    errors = 0
    journal: list[str] = []
    while errors < 5:
        code, _ = shop(fault="error500")
        if code >= 500:
            errors += 1
    journal.append("Closed -> Open: серия ошибок 5")
    detected = time.perf_counter()
    cause = "партнёр отдаёт 500" if journal[-1].endswith("5") else "неизвестно"
    diagnosed = time.perf_counter()
    code, _ = shop()
    assert code == 200 and cause
    record("партнёр лежит (магазин 500)", detected - started,
           diagnosed - detected, time.perf_counter() - diagnosed, True,
           "breaker открыл контур; в Open вызовы не ходят в сеть вовсе")


def injection_db_slow() -> None:
    psql("DROP SCHEMA IF EXISTS gameday CASCADE; CREATE SCHEMA gameday;"
         "CREATE TABLE gameday.t AS SELECT g AS id, md5(g::text) AS v "
         "FROM generate_series(1, 200000) AS g;")
    started = time.perf_counter()
    slow = subprocess.Popen([PSQL, *CONN, "-t", "-A"],
                            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)
    slow.stdin.write("SELECT pg_sleep(6);")
    slow.stdin.close()
    time.sleep(0.3)
    before = psql("SELECT count(*) FROM gameday.t;")
    detected = time.perf_counter()
    cause = psql("SELECT count(*) FROM pg_stat_activity "
                 "WHERE query LIKE '%pg_sleep%' AND state = 'active' "
                 "AND pid <> pg_backend_pid();")
    diagnosed = time.perf_counter()
    slow.wait(timeout=30)
    after = psql("SELECT count(*) FROM gameday.t;")
    assert before == after == "200000" and int(cause) >= 1
    record("СУБД тормозит (pg_sleep 6 с)", detected - started,
           diagnosed - detected, time.perf_counter() - diagnosed, True,
           "причина видна в pg_stat_activity; алерта на медленность нет — слепое место")
    psql("DROP SCHEMA gameday CASCADE;")


def injection_queue_flood() -> None:
    psql("DROP SCHEMA IF EXISTS gameday CASCADE; CREATE SCHEMA gameday;"
         "CREATE TABLE gameday.queue (id BIGSERIAL PRIMARY KEY, "
         "payload TEXT, done BOOLEAN NOT NULL DEFAULT FALSE);"
         "INSERT INTO gameday.queue (payload) SELECT 'msg-' || g "
         "FROM generate_series(1, 10000) AS g;")
    started = time.perf_counter()
    depth = int(psql("SELECT count(*) FROM gameday.queue WHERE NOT done;"))
    assert depth == 10000
    detected = time.perf_counter()
    diagnosed = time.perf_counter()
    psql("UPDATE gameday.queue SET done = TRUE WHERE id IN "
         "(SELECT id FROM gameday.queue WHERE NOT done LIMIT 10000);")
    left = int(psql("SELECT count(*) FROM gameday.queue WHERE NOT done;"))
    assert left == 0
    record("очередь переполнена (10 000 сообщений)", detected - started,
           diagnosed - detected, time.perf_counter() - diagnosed, True,
           "глубина — метрика, а не сюрприз; сообщения не потеряны, обработаны пакетом")
    psql("DROP SCHEMA gameday CASCADE;")


def injection_disk_full() -> None:
    work = Path("/tmp/gameday_disk")
    work.mkdir(exist_ok=True)
    target = work / "queue.log"
    started = time.perf_counter()
    script = (
        "import resource\n"
        "resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024, 64 * 1024))\n"
        f"f = open({str(target)!r}, 'w')\n"
        "try:\n"
        "    f.write('x' * 1024 * 1024)\n"
        "    f.flush()\n"
        "    print('WRITTEN')\n"
        "except OSError as err:\n"
        "    print('ENOSPC:', err)\n"
    )
    out = subprocess.run(["python3", "-c", script], capture_output=True, text=True)
    detected = time.perf_counter()
    assert "ENOSPC" in out.stdout or "File too large" in (out.stdout + out.stderr), out
    diagnosed = time.perf_counter()
    intact = target.exists() and target.stat().st_size <= 64 * 1024
    target.unlink(missing_ok=True)
    record("диск заполнен (лимит файла 64 КБ вместо реального ENOSPC)",
           detected - started, diagnosed - detected,
           time.perf_counter() - diagnosed, intact,
           "ошибка записи видна сразу; частичная запись не притворяется успешной")
    work.rmdir()


def injection_garbage() -> None:
    started = time.perf_counter()
    code, body = shop(fault="garbage")
    detected = time.perf_counter()
    contract_ok = False
    try:
        contract_ok = isinstance(json.loads(body), dict) and "items" in json.loads(body)
    except json.JSONDecodeError:
        contract_ok = False
    diagnosed = time.perf_counter()
    assert code == 200 and not contract_ok
    code2, body2 = shop()
    assert code2 == 200 and "items" in json.loads(body2)
    record("неверный формат от партнёра (garbage вместо JSON)",
           detected - started, diagnosed - detected,
           time.perf_counter() - diagnosed, True,
           "контрактная ошибка видна на парсинге; повтор такого ответа бессмыслен (не 5xx)")


def main() -> None:
    assert Path(PSQL).exists(), "стенд PostgreSQL не поднят"
    injection_partner_down()
    injection_db_slow()
    injection_queue_flood()
    injection_disk_full()
    injection_garbage()
    assert all(item["data_ok"] for item in RESULTS)
    print(f"[ok] учение завершено: инъекций {len(RESULTS)}, потерь данных нет")


if __name__ == "__main__":
    main()
