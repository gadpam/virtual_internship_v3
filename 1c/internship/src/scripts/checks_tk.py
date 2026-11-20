#!/usr/bin/env python3
"""Проверки task_93: клиент ТК — лимит, Retry-After, метрики (зеркало).

Свой экземпляр mock_tk_api с лимитом 6/мин: расчёт и заявка работают,
серия запросов упирается в 429, клиент читает Retry-After, ждёт и
успешно повторяет. Параллельность ограничена семафором на 4.

Запуск: TK_URL=http://127.0.0.1:8032, экземпляр поднят с
MOCK_TK_RATE_LIMIT=6: src/scripts/.venv/bin/python src/scripts/checks_tk.py
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
import uuid

BASE = os.environ.get("TK_URL", "http://127.0.0.1:8032")
KEY = "mock-tk-key"
METRICS = {"requests": 0, "rate_limited": 0, "total_ms": 0.0}
SEMAPHORE = threading.Semaphore(4)
INFLIGHT = {"now": 0, "max": 0}
LOCK = threading.Lock()


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict, dict]:
    req = urllib.request.Request(BASE + path, method=method)
    req.add_header("X-Api-Key", KEY)
    if body is not None:
        req.add_header("Content-Type", "application/json")
        req.data = json.dumps(body).encode()
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = (resp.status, json.loads(resp.read().decode()), dict(resp.headers))
    except urllib.error.HTTPError as err:
        result = (err.code, json.loads(err.read().decode() or "{}"), dict(err.headers))
    METRICS["requests"] += 1
    METRICS["total_ms"] += (time.perf_counter() - start) * 1000
    if result[0] == 429:
        METRICS["rate_limited"] += 1
    return result


def limited_calculate(i: int) -> None:
    with SEMAPHORE:
        with LOCK:
            INFLIGHT["now"] += 1
            INFLIGHT["max"] = max(INFLIGHT["max"], INFLIGHT["now"])
        try:
            call("POST", "/api/v1/calculate",
                 {"city_to": "Брест", "weight_kg": 1 + i * 0.1, "volume_m3": 0.01})
        finally:
            with LOCK:
                INFLIGHT["now"] -= 1


def main() -> None:
    status, price, _ = call("POST", "/api/v1/calculate",
                            {"city_to": "Брест", "weight_kg": 2.5, "volume_m3": 0.03})
    assert status == 200 and price["price"] > 0, price
    print(f"[ok] расчёт: {price['price']} {price['currency']} до {price['cityTo']}")

    ext = "SHOP-T93-" + uuid.uuid4().hex[:6]
    status, shipment, _ = call("POST", "/api/v1/shipments",
                               {"external_id": ext, "city_to": "Брест", "weight_kg": 2.5})
    assert status == 201 and shipment["status"] == "created", shipment
    status, again, _ = call("POST", "/api/v1/shipments",
                            {"external_id": ext, "city_to": "Брест", "weight_kg": 2.5})
    assert again["duplicate"] is True and again["shipmentId"] == shipment["shipmentId"]
    print(f"[ok] заявка {shipment['shipmentId']}: повтор по external_id — duplicate")

    # Лимит своего экземпляра: 6/мин. Уже сделано 3 запроса — серия добьёт до 429.
    retry_after = None
    for _ in range(8):
        status, _, headers = call("POST", "/api/v1/calculate",
                                  {"city_to": "Витебск", "weight_kg": 1, "volume_m3": 0.01})
        if status == 429:
            # Заголовки HTTP регистронезависимы: ищем без учёта регистра,
            # иначе «пауза» окажется значением по умолчанию, а не партнёра.
            lowered = {k.lower(): v for k, v in headers.items()}
            retry_after = int(lowered.get("retry-after", "1"))
            break
    assert retry_after is not None, "серия не упёрлась в лимит"
    print(f"[ok] получен 429, Retry-After: {retry_after} с — ждём честно")
    time.sleep(retry_after + 1)
    status, price, _ = call("POST", "/api/v1/calculate",
                            {"city_to": "Витебск", "weight_kg": 1, "volume_m3": 0.01})
    assert status == 200, status
    print("[ok] после паузы по Retry-After запрос прошёл")

    threads = [threading.Thread(target=limited_calculate, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert INFLIGHT["max"] <= 4
    print(f"[ok] параллельность ограничена: максимум одновременных {INFLIGHT['max']} из 4")

    avg = METRICS["total_ms"] / METRICS["requests"]
    print(f"[ok] метрики прогона: запросов {METRICS['requests']}, "
          f"429: {METRICS['rate_limited']}, среднее {avg:.0f} мс")


if __name__ == "__main__":
    main()
