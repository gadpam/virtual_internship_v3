#!/usr/bin/env python3
"""Проверки task_111: семантика брокера (зеркало; RabbitMQ в среде нет).

Модель повторяет контракт стенда: exchange с routing key, ack только
после обработки, nack+requeue временной ошибки, DLQ постоянной,
неподтверждённое сообщение возвращается при «падении» потребителя.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_broker.py
"""

from __future__ import annotations

from collections import deque


class Broker:
    def __init__(self) -> None:
        self.queues: dict[str, deque] = {}
        self.bindings: dict[str, list[str]] = {}
        self.dlq: list[dict] = []

    def bind(self, queue: str, routing_key: str) -> None:
        self.queues.setdefault(queue, deque())
        self.bindings.setdefault(routing_key, []).append(queue)

    def publish(self, routing_key: str, body: dict) -> int:
        delivered = 0
        for queue in self.bindings.get(routing_key, []):
            self.queues[queue].append({"body": body, "retries": 0, "acked": False})
            delivered += 1
        return delivered


def consume_once(broker: Broker, queue: str, handler) -> str:
    if not broker.queues[queue]:
        return "empty"
    msg = broker.queues[queue][0]
    try:
        handler(msg["body"])
    except ValueError:
        broker.queues[queue].popleft()
        broker.dlq.append(msg)
        return "dlq"
    except RuntimeError:
        msg["retries"] += 1
        broker.queues[queue].rotate(-1)
        return "requeue"
    broker.queues[queue].popleft()
    msg["acked"] = True
    return "ack"


def main() -> None:
    broker = Broker()
    broker.bind("rih.orders.in", "document.posted")
    broker.bind("rih.audit", "document.posted")
    event = {"event": "document.posted", "version": 1, "documentId": "doc-1"}
    assert broker.publish("document.posted", event) == 2
    assert broker.publish("unknown.key", event) == 0
    print("[ok] exchange разносит событие по binding: 2 очереди, чужие ключи — 0")

    delivered: list[str] = []
    assert consume_once(broker, "rih.orders.in", lambda b: delivered.append(b["documentId"])) == "ack"
    assert delivered == ["doc-1"]
    print("[ok] потребитель обработал и подтвердил (ack после обработки)")

    broker2 = Broker()
    broker2.bind("q", "k")
    broker2.publish("k", {"event": "document.posted", "version": 1, "documentId": "doc-2"})
    attempts = {"n": 0}

    def flaky(body: dict) -> None:
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("временная недоступность RIH")

    assert consume_once(broker2, "q", flaky) == "requeue"
    assert consume_once(broker2, "q", flaky) == "ack"
    print("[ok] временная ошибка: nack+requeue, со второй попытки — ack, сообщение не потеряно")

    broker3 = Broker()
    broker3.bind("q", "k")
    broker3.publish("k", {"event": "document.posted", "version": 1, "documentId": "doc-3"})

    def broken(body: dict) -> None:
        raise ValueError("постоянная ошибка формата")

    assert consume_once(broker3, "q", broken) == "dlq" and len(broker3.dlq) == 1
    print("[ok] постоянная ошибка: сообщение в DLQ, а не в бесконечном повторе")


if __name__ == "__main__":
    main()
