"""Точка входа консьюмера: корректный ack/nack, ретраи, DLQ.

Паттерн из task_110, task_112 и task_128: подтверждение только после успешной обработки,
ограниченное число повторов, мёртвая очередь для постоянных ошибок.
"""
import asyncio
import json
import logging
import signal
from typing import Optional

import aio_pika
import httpx
from aio_pika.abc import AbstractIncomingMessage

from app.config import load_settings

settings = load_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("queue_consumer")

RETRY_HEADER = "x-retry-count"
TEMPORARY_STATUSES = {408, 429, 500, 502, 503, 504}
stop_event = asyncio.Event()


def _retry_count(message: AbstractIncomingMessage) -> int:
    raw = message.headers.get(RETRY_HEADER)
    try:
        return int(raw) if raw is not None else 0
    except (TypeError, ValueError):
        return 0


async def forward_to_rih(client: httpx.AsyncClient, body: bytes) -> int:
    """Отправляет сообщение в HTTP-сервис 1С и возвращает код ответа."""
    response = await client.post(
        settings.rih_http_url,
        content=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        timeout=settings.timeout,
    )
    return response.status_code


async def handle(client: httpx.AsyncClient, message: AbstractIncomingMessage) -> None:
    attempt = _retry_count(message)
    correlation_id = message.headers.get("correlationId") or message.message_id or "-"

    async with message.process(ignore_processed=True):
        try:
            status = await forward_to_rih(client, message.body)
        except (httpx.TransportError, httpx.TimeoutException) as error:
            logger.warning("correlationId=%s сеть недоступна: %s", correlation_id, error)
            status = 503

        if 200 <= status < 300:
            logger.info("correlationId=%s обработано (%d)", correlation_id, status)
            await message.ack()
            return

        if status not in TEMPORARY_STATUSES:
            logger.error("correlationId=%s постоянная ошибка (%d) → DLQ", correlation_id, status)
            await message.nack(requeue=False)
            return

        if attempt + 1 >= settings.max_retries:
            logger.error("correlationId=%s исчерпаны попытки (%d/%d) → DLQ",
                         correlation_id, attempt + 1, settings.max_retries)
            await message.nack(requeue=False)
            return

        delay = min(2 ** attempt, 30)  # экспоненциальная задержка (task_128)
        logger.warning("correlationId=%s временная ошибка (%d), повтор %d через %d с",
                       correlation_id, status, attempt + 1, delay)
        await asyncio.sleep(delay)
        await message.nack(requeue=True)


async def run() -> None:
    logger.info("подключение к %s, очередь %s", settings.amqp_url, settings.queue_name)
    connection: Optional[aio_pika.RobustConnection] = None
    try:
        connection = await aio_pika.connect_robust(settings.amqp_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=settings.prefetch)

        queue = await channel.declare_queue(settings.queue_name, durable=True)
        # DLQ объявляем заранее: nack(requeue=False) в RabbitMQ без политики
        # x-dead-letter-exchange просто удаляет сообщение. В учебном стенде
        # политику настраивает tools/rabbitmq/definitions.json (task_111).
        await channel.declare_queue(settings.dlq_name, durable=True)

        async with httpx.AsyncClient() as client:
            async with queue.iterator() as iterator:
                async for message in iterator:
                    if stop_event.is_set():
                        break
                    await handle(client, message)
    finally:
        if connection is not None:
            await connection.close()
        logger.info("консьюмер остановлен")


def _install_signal_handlers() -> None:
    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop_event.set)


def main() -> None:
    try:
        _install_signal_handlers()
    except NotImplementedError:  # Windows без Proactor-цикла
        pass
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        logger.info("остановлено пользователем")


if __name__ == "__main__":
    main()
