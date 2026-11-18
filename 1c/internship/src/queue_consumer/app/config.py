"""Настройки консьюмера из переменных окружения."""
import os
from dataclasses import dataclass

try:  # локальная разработка с .env
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # в контейнере переменные приходят из окружения
    pass


@dataclass(frozen=True)
class Settings:
    amqp_url: str
    queue_name: str
    dlq_name: str
    rih_http_url: str
    max_retries: int
    prefetch: int
    timeout: float
    log_level: str


def load_settings() -> Settings:
    return Settings(
        amqp_url=os.getenv("AMQP_URL", "amqp://guest:guest@localhost:5672/"),
        queue_name=os.getenv("QUEUE_NAME", "rih.orders.in"),
        dlq_name=os.getenv("DLQ_NAME", "rih.orders.in.dlq"),
        rih_http_url=os.getenv("RIH_HTTP_URL", "http://localhost:8009/hs/rih/v1/queue/incoming"),
        max_retries=int(os.getenv("MAX_RETRIES", "3")),
        prefetch=int(os.getenv("PREFETCH", "10")),
        timeout=float(os.getenv("REQUEST_TIMEOUT_SECONDS", "10")),
        log_level=os.getenv("LOG_LEVEL", "INFO"),
    )
