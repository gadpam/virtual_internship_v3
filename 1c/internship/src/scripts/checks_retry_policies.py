#!/usr/bin/env python3
"""Проверки task_128: политика повторов и шторм повторов (зеркало).

Классификация ошибок таблицей; эксперимент: партнёр лежит 3 с (503),
100 клиентов стартуют одновременно. Три политики: без повторов,
фиксированная пауза, экспонента с джиттером. Меряем долю успеха,
среднее число попыток и пик запросов в секунду на партнёре — шторм
виден цифрой, а не метафорой. Масштаб задержек уменьшен (база 0.2 с
вместо 1 с боевой политики): форма кривых та же.

Живой mock_shop_api :8026: 500 повторяется до лимита, 400/401 — нет.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_retry_policies.py
"""

from __future__ import annotations

import json
import os
import random
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer


class FastServer(HTTPServer):
    # Однопоточный сервер с большой очередью приёма: потоковый
    # в этой среде не тянет 100 одновременных соединений, а ответы
    # эксперимента мгновенны — сериализация приёма честнее шторма.
    request_queue_size = 256
    daemon_threads = True

SHOP = os.environ.get("MOCK_SHOP_URL", "http://127.0.0.1:8026")
SHOP_KEY = os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key")
RETRYABLE = {0, 408, 429, 500, 502, 503, 504}
DOWN_SECONDS = 2.5
CLIENTS = 100


def retryable(code: int) -> bool:
    return code in RETRYABLE


def delay(policy: str, attempt: int) -> float:
    if policy == "fixed":
        return 0.5
    base = 0.2 * (2 ** (attempt - 2))
    return base + random.uniform(0, 0.2)


class FlakyHandler(BaseHTTPRequestHandler):
    started = 0.0
    buckets: dict[int, int] = {}
    lock = threading.Lock()

    def do_GET(self) -> None:  # noqa: N802
        with FlakyHandler.lock:
            second = int((time.time() - FlakyHandler.started) * 10)
            FlakyHandler.buckets[second] = FlakyHandler.buckets.get(second, 0) + 1
        down = time.time() - FlakyHandler.started < DOWN_SECONDS
        payload = b'{"ok": true}'
        self.send_response(503 if down else 200)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, *args) -> None:
        pass


def call_with_policy(port: int, policy: str) -> tuple[bool, int]:
    limit = 1 if policy == "none" else 10
    attempts = 0
    while attempts < limit:
        attempts += 1
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/ping", timeout=5) as resp:
                resp.read()
                return True, attempts
        except urllib.error.HTTPError as err:
            if not retryable(err.code):
                return False, attempts
        except (urllib.error.URLError, TimeoutError):
            pass
        if attempts < limit:
            time.sleep(delay(policy, attempts + 1))
    return False, attempts


def experiment(port: int, policy: str) -> dict:
    FlakyHandler.started = time.time()
    FlakyHandler.buckets = {}
    barrier = threading.Barrier(CLIENTS)

    def job(_: int) -> tuple[bool, int]:
        barrier.wait()
        return call_with_policy(port, policy)

    with ThreadPoolExecutor(max_workers=CLIENTS) as pool:
        results = list(pool.map(job, range(CLIENTS)))
    ok = sum(1 for success, _ in results if success)
    attempts = [count for _, count in results]
    # Пик — только повторная волна (после 0.3 с): стартовый всплеск
    # всех клиентов в первое окно есть у любой политики и не шторм.
    retry_buckets = [count for second, count in FlakyHandler.buckets.items() if second >= 3]
    peak = max(retry_buckets) * 10 if retry_buckets else 0
    total = sum(FlakyHandler.buckets.values())
    return {"policy": policy, "success_pct": round(100 * ok / CLIENTS, 1),
            "avg_attempts": round(sum(attempts) / len(attempts), 2),
            "peak_rps": peak, "total_requests": total}


def shop_call(fault: str | None, key: str = SHOP_KEY) -> tuple[int, int]:
    attempts = 0
    while attempts < 3:
        attempts += 1
        req = urllib.request.Request(f"{SHOP}/api/v1/products")
        req.add_header("X-Api-Key", key)
        if fault:
            req.add_header("X-Fault-Mode", fault)
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                resp.read()
                return resp.status, attempts
        except urllib.error.HTTPError as err:
            if not retryable(err.code) or attempts >= 3:
                return err.code, attempts
        except (urllib.error.URLError, TimeoutError):
            if attempts >= 3:
                return 0, attempts
        time.sleep(delay("exp", attempts + 1))
    return 0, attempts


def main() -> None:
    for code in (429, 500, 502, 503, 504, 0):
        assert retryable(code), code
    for code in (400, 401, 403, 404, 409, 422):
        assert not retryable(code), code
    print("[ok] классификация: повторяемые 429/5xx/таймаут; 400/401/403/404/409/422 — нет")

    server = FastServer(("127.0.0.1", 0), FlakyHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        none = experiment(port, "none")
        fixed = experiment(port, "fixed")
        expo = experiment(port, "exp")
    finally:
        server.shutdown()
    print(f"[ok] без повторов: успех {none['success_pct']}%, попыток {none['avg_attempts']}, "
          f"запросов {none['total_requests']}")
    print(f"[ok] фикс. пауза 0.5 с: успех {fixed['success_pct']}%, попыток {fixed['avg_attempts']}, "
          f"пик {fixed['peak_rps']} запр/с, запросов {fixed['total_requests']}")
    print(f"[ok] экспонента+джиттер: успех {expo['success_pct']}%, попыток {expo['avg_attempts']}, "
          f"пик {expo['peak_rps']} запр/с, запросов {expo['total_requests']}")
    assert none["success_pct"] == 0.0
    assert fixed["success_pct"] > 90 and expo["success_pct"] > 90
    assert expo["peak_rps"] < fixed["peak_rps"], (expo, fixed)
    print("[ok] вывод: обе политики с повторами поднимают клиентов, но пила "
          "фиксированной паузы бьёт по партнёру пиком; джиттер размазывает волну")

    code, attempts = shop_call("error500")
    assert code == 500 and attempts == 3, (code, attempts)
    code400, attempts400 = shop_call("unknown-mode")
    assert code400 == 400 and attempts400 == 1, (code400, attempts400)
    print(f"[ok] живой магазин :8026: 500 — исчерпаны 3 попытки политики; "
          f"400 — ровно 1 попытка (повторять свою ошибку бессмысленно)")


if __name__ == "__main__":
    main()
