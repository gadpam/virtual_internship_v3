"""Экспортёр: читает JSON-метрики из 1С и отдаёт /metrics в формате Prometheus."""
import asyncio
import logging
import os
import time
from typing import Dict, List, Tuple

import httpx
from fastapi import FastAPI, Response

from app.prometheus import counter, gauge, histogram

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

METRICS_URL = os.getenv("RIH_METRICS_URL", "http://localhost:8009/hs/rih/v1/metrics")
METRICS_USER = os.getenv("RIH_METRICS_USER") or None
METRICS_PASSWORD = os.getenv("RIH_METRICS_PASSWORD") or None
TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "5"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("metrics_exporter")

app = FastAPI(title="RIH metrics exporter", version="1.0.0")

# Кэш последнего успешного снимка: при недоступной 1С отдаём его с меткой stale.
CACHE: Dict[str, object] = {"payload": None, "fetched_at": 0.0, "up": 0}
LOCK = asyncio.Lock()


async def fetch_payload() -> Tuple[Dict[str, object], bool]:
    """Возвращает (полезная нагрузка, жива ли 1С)."""
    auth = httpx.BasicAuth(METRICS_USER, METRICS_PASSWORD) if METRICS_USER else None
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT, auth=auth) as client:
            response = await client.get(METRICS_URL)
            response.raise_for_status()
            payload = response.json()
            CACHE["payload"] = payload
            CACHE["fetched_at"] = time.time()
            CACHE["up"] = 1
            return payload, True
    except (httpx.HTTPError, ValueError) as error:
        logger.warning("не удалось получить метрики 1С: %s", error)
        CACHE["up"] = 0
        cached = CACHE["payload"]
        if cached is None:
            return {}, False
        return cached, False


def build_text(payload: Dict[str, object], alive: bool) -> str:
    lines: List[str] = []
    stale = "" if alive else 'stale="true"'

    requests: List[Tuple[Dict[str, str], float]] = []
    for item in payload.get("integrationRequests", []) or []:
        labels = {
            "system": str(item.get("system", "unknown")),
            "operation": str(item.get("operation", "unknown")),
            "status": str(item.get("status", "unknown")),
        }
        requests.append((labels, float(item.get("count", 0))))
    lines += counter(
        "rih_integration_requests_total",
        "Количество обращений интеграций RIH по системам и исходам",
        requests,
    )

    durations: List[Tuple[Dict[str, str], List[float]]] = []
    for item in payload.get("durations", []) or []:
        labels = {
            "system": str(item.get("system", "unknown")),
            "operation": str(item.get("operation", "unknown")),
        }
        durations.append((labels, [float(v) for v in item.get("samples", []) or []]))
    lines += histogram(
        "rih_integration_duration_seconds",
        "Длительность интеграционных обращений, секунды",
        durations,
    )

    depths = [
        ({"queue": str(item.get("queue", "unknown")), "state": str(item.get("state", "unknown"))},
         float(item.get("depth", 0)))
        for item in payload.get("queueDepth", []) or []
    ]
    lines += gauge("rih_queue_depth", "Глубина очередей RIH", depths)

    errors = [
        ({"system": str(item.get("system", "unknown")), "code": str(item.get("code", "unknown"))},
         float(item.get("count", 0)))
        for item in payload.get("errors", []) or []
    ]
    lines += counter("rih_errors_total", "Ошибки интеграций по кодам", errors)

    lags = [
        ({"plan": str(item.get("plan", "unknown")), "direction": str(item.get("direction", "unknown"))},
         float(item.get("lagSeconds", 0)))
        for item in payload.get("exchangeLag", []) or []
    ]
    lines += gauge("rih_exchange_lag_seconds", "Отставание обменов от расписания, секунды", lags)

    breaker_states = {"Closed": 0, "Open": 1, "HalfOpen": 2}
    breakers = [
        ({"circuit": str(item.get("circuit", "unknown"))},
         float(breaker_states.get(str(item.get("state", "Closed")), 0)))
        for item in payload.get("breakers", []) or []
    ]
    lines += gauge(
        "rih_circuit_breaker_state",
        "Состояние предохранителей: 0=Closed, 1=Open, 2=HalfOpen (task_129)",
        breakers,
    )

    lines += gauge(
        "rih_up",
        "Доступность источников метрик (1 = жив)",
        [({"service": "rih_1c"}, 1 if alive else 0)],
    )
    lines += gauge(
        "rih_exporter_last_scrape_timestamp_seconds",
        "Метка времени последнего успешного получения метрик",
        [({}, float(CACHE["fetched_at"] or 0))],
    )

    if stale:
        # Комментарий в тексте — не метка, но полезен при разборе руками
        lines.insert(0, "# WARNING: источник метрик недоступен, отдаётся последний снимок")
    return "\n".join(lines) + "\n"


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "source": METRICS_URL, "up": CACHE["up"]}


@app.get("/metrics")
async def metrics() -> Response:
    async with LOCK:
        payload, alive = await fetch_payload()
    return Response(content=build_text(payload, alive), media_type="text/plain; version=0.0.4; charset=utf-8")
