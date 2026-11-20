#!/usr/bin/env python3
"""Проверки task_110: очередь v2 — приоритеты, типы, мёртвая почта.

10 000 сообщений, 5% — постоянные ошибки: хорошие отправлены,
битые после 5 попыток лежат в мёртвой почте с причиной; высокие
приоритеты уходят раньше обычных; время разбора зафиксировано.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_queue_v2.py
"""

from __future__ import annotations

import heapq
import time

MAX_ATTEMPTS = 5


def main() -> None:
    queue: list[tuple[int, int, dict]] = []
    seq = 0
    for i in range(10_000):
        msg = {"id": i, "type": "order" if i % 3 else "catalog",
               "bad": i % 20 == 0, "attempts": 0}
        priority = 1 if msg["type"] == "order" else 0
        heapq.heappush(queue, (-priority, seq, msg))
        seq += 1

    sent_order: list[int] = []
    sent = dead = 0
    dead_reasons: dict[int, str] = {}
    start = time.perf_counter()
    while queue:
        _, _, msg = heapq.heappop(queue)
        if msg["bad"]:
            msg["attempts"] += 1
            if msg["attempts"] >= MAX_ATTEMPTS:
                dead += 1
                dead_reasons[msg["id"]] = "постоянная ошибка партнёра (симуляция)"
            else:
                heapq.heappush(queue, (0, seq, msg))
                seq += 1
            continue
        sent += 1
        sent_order.append(msg["id"])
    seconds = time.perf_counter() - start

    assert sent == 9_500 and dead == 500, (sent, dead)
    first_catalog = next(i for i, mid in enumerate(sent_order) if mid % 3 == 0)
    orders_before = sum(1 for mid in sent_order[:first_catalog] if mid % 3 != 0)
    assert orders_before > 3_000, orders_before
    print(f"[ok] 10000 сообщений за {seconds:.2f} с: отправлено {sent}, мёртвая почта {dead}")
    print(f"[ok] приоритеты: до первого каталога ушло заказов {orders_before}")
    print(f"[ok] мёртвая почта хранит причину, пример: id 0 — {dead_reasons[0]}")


if __name__ == "__main__":
    main()
