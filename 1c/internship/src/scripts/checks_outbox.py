#!/usr/bin/env python3
"""Проверки task_95: исходящая очередь обмена (зеркало РИХ_ОчередьОбмена).

Сценарий деградации ускоренно: партнёр «лежит» (мёртвый порт) — 500
сообщений копятся со статусами повторов; партнёр «встал» (свой mock
магазина) — очередь уходит пакетом. Ядовитое сообщение исчерпывает
5 попыток и ждёт оператора; действия оператора проверяются.

Запуск: SHOP_EXPORT_URL=http://127.0.0.1:8031 \
  src/scripts/.venv/bin/python src/scripts/checks_outbox.py
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid

SHOP = os.environ.get("SHOP_EXPORT_URL", "http://127.0.0.1:8031")
KEY = os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key")
MAX_ATTEMPTS = 5


class Queue:
    def __init__(self) -> None:
        self.messages: dict[str, dict] = {}

    def put(self, body: dict, key: str) -> str:
        mid = uuid.uuid4().hex[:12]
        self.messages[mid] = {"body": body, "key": key, "status": "Новая",
                              "attempts": 0, "next_at": 0.0, "error": ""}
        return mid

    def process(self, sender, now: float, limit: int = 1000) -> dict:
        result = {"sent": 0, "deferred": 0, "failed": 0}
        for mid, msg in list(self.messages.items())[:limit]:
            if msg["status"] not in ("Новая", "Отложена") or msg["next_at"] > now:
                continue
            try:
                sender(msg)
                msg["status"] = "Отправлена"
                result["sent"] += 1
            except Exception as err:  # очередь честно фиксирует любой отказ
                msg["attempts"] += 1
                msg["error"] = str(err)[:120]
                if msg["attempts"] >= MAX_ATTEMPTS:
                    msg["status"] = "Ошибка"
                    result["failed"] += 1
                else:
                    msg["status"] = "Отложена"
                    msg["next_at"] = now + (2 ** (msg["attempts"] - 1)) * 0.01  # минуты→шкала теста
                    result["deferred"] += 1
        return result


def send_order(base: str):
    def sender(msg: dict) -> None:
        req = urllib.request.Request(base + "/api/v1/orders", method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Api-Key", KEY)
        req.add_header("Idempotency-Key", msg["key"])
        req.data = json.dumps(msg["body"]).encode()
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 201):
                raise RuntimeError(f"HTTP {resp.status}")
    return sender


RUN = uuid.uuid4().hex[:6]


def order(i: int) -> dict:
    # external_id уникален на прогон: магазин отвечает 409 на тот же
    # external_id с другим ключом идемпотентности — это контракт, не сбой.
    return {"external_id": f"OUTBOX-{RUN}-{i:04d}", "customer_ref": "CL-1",
            "lines": [{"sku": "SKU-00001", "quantity": 1, "price": 10.0}],
            "created_at": "2026-11-17T10:00:00Z"}


def main() -> None:
    queue = Queue()
    for i in range(500):
        queue.put(order(i), str(uuid.uuid4()))

    dead = send_order("http://127.0.0.1:9999")
    now = time.monotonic()
    result = queue.process(dead, now)
    assert result == {"sent": 0, "deferred": 500, "failed": 0}, result
    waiting = sum(1 for m in queue.messages.values() if m["status"] == "Отложена")
    print(f"[ok] партнёр лежит: накоплено {waiting}, отправлено 0 — продажи не откатились")

    alive = send_order(SHOP)
    result = queue.process(alive, time.monotonic() + 100)
    assert result["sent"] == 500, result
    print(f"[ok] партнёр встал: пакетом отправлено {result['sent']}, очередь пуста")

    poison_id = queue.put({"external_id": "OUTBOX-POISON", "customer_ref": "CL-1",
                           "lines": [], "created_at": "2026-11-17T10:00:00Z"}, str(uuid.uuid4()))
    now = time.monotonic()
    for step in range(MAX_ATTEMPTS):
        queue.process(alive, now + 100 + step)  # время теста идёт вперёд, паузы истекают
    poison = queue.messages[poison_id]
    assert poison["status"] == "Ошибка" and poison["attempts"] == 5, poison
    print(f"[ok] ядовитое сообщение: 5 попыток → «Ошибка», последняя: {poison['error'][:40]}")

    poison["status"] = "Новая"
    poison["attempts"] = 0
    poison["next_at"] = 0.0  # как ИсправитьСообщение в РИХ_ОчередьОбмена: срок — сейчас
    poison["body"] = order(9999)
    result = queue.process(alive, time.monotonic() + 100)
    assert queue.messages[poison_id]["status"] == "Отправлена"
    print("[ok] оператор исправил тело и повторил — сообщение отправлено")


if __name__ == "__main__":
    main()
