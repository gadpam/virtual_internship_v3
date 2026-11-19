"""Mock API транспортной компании (task_93, task_130, task_143).

Реализует rate limiting (429 + Retry-After) и режимы сбоев для отладки
ретраев, circuit breaker и деградации.
"""
import asyncio
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Deque, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel, Field

API_KEY = os.getenv("MOCK_TK_API_KEY", "mock-tk-key")
RATE_LIMIT = int(os.getenv("MOCK_TK_RATE_LIMIT", "10"))
RATE_WINDOW_SECONDS = 60

app = FastAPI(title="Mock Transport Company API", version="1.0.0")

_hits: Dict[str, Deque[float]] = defaultdict(deque)
SHIPMENTS: Dict[str, dict] = {}


class CalculateRequest(BaseModel):
    city_to: str
    weight_kg: float = Field(..., gt=0)
    volume_m3: float = Field(..., gt=0)
    declared_value: float = Field(0.0, ge=0)


class ShipmentRequest(BaseModel):
    external_id: str
    city_to: str
    weight_kg: float = Field(..., gt=0)
    comment: Optional[str] = None


def _check_key(x_api_key: Optional[str]) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="не указан X-Api-Key")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="неверный X-Api-Key")
    return x_api_key


def _apply_rate_limit(key: str) -> None:
    """Скользящее окно: не более RATE_LIMIT запросов за RATE_WINDOW_SECONDS."""
    now = time.time()
    window = _hits[key]
    while window and window[0] < now - RATE_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT:
        retry_after = int(RATE_WINDOW_SECONDS - (now - window[0])) + 1
        raise HTTPException(
            status_code=429,
            detail="превышен лимит запросов транспортной компании",
            headers={"Retry-After": str(max(retry_after, 1))},
        )
    window.append(now)


async def _apply_fault(mode: Optional[str]) -> None:
    mode = (mode or "").lower()
    if mode in ("", "ok"):
        return
    if mode == "error500":
        raise HTTPException(status_code=500, detail="mock: сбой на стороне ТК")
    if mode == "timeout":
        await asyncio.sleep(35)
        return
    if mode == "slow":
        await asyncio.sleep(4)
        return
    if mode == "garbage":
        raise HTTPException(status_code=502, detail="<html>не JSON</html>")
    if mode == "label_failed":
        raise HTTPException(status_code=503, detail="mock: сервис этикеток недоступен")
    raise HTTPException(status_code=400, detail=f"mock: неизвестный режим '{mode}'")


@app.post("/__reset__")
def reset_state(x_api_key: Optional[str] = Header(default=None)) -> dict:
    """Сброс состояния для тестового стенда: окна rate limit и заявки.

    Нужен интеграционным тестам (task_141): иначе тесты делят лимит
    10/мин и влияют друг на друга порядком запуска.
    """
    _check_key(x_api_key)
    _hits.clear()
    SHIPMENTS.clear()
    return {"status": "reset", "shipments": 0}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock_tk_api", "rate_limit_per_minute": RATE_LIMIT,
            "shipments": len(SHIPMENTS)}


@app.post("/api/v1/calculate")
async def calculate(
    payload: CalculateRequest,
    request: Request,
    x_api_key: Optional[str] = Header(default=None),
    x_fault_mode: Optional[str] = Header(default=None),
) -> dict:
    _check_key(x_api_key)
    _apply_rate_limit(x_api_key)
    await _apply_fault(x_fault_mode)
    base = 5.0
    weight_price = payload.weight_kg * 0.8
    volume_price = payload.volume_m3 * 12.0
    total = round(base + weight_price + volume_price, 2)
    return {
        "cityTo": payload.city_to,
        "price": total,
        "currency": "BYN",
        "deliveryDays": 1 + int(payload.weight_kg // 20),
        "calculatedAt": datetime.now(timezone.utc).isoformat(),
    }


@app.post("/api/v1/shipments", status_code=201)
async def create_shipment(
    payload: ShipmentRequest,
    x_api_key: Optional[str] = Header(default=None),
    x_fault_mode: Optional[str] = Header(default=None),
) -> dict:
    _check_key(x_api_key)
    _apply_rate_limit(x_api_key)
    await _apply_fault(x_fault_mode)

    existing = next((s for s in SHIPMENTS.values() if s["externalId"] == payload.external_id), None)
    if existing:
        return {**existing, "duplicate": True}

    shipment = {
        "shipmentId": str(uuid.uuid4()),
        "externalId": payload.external_id,
        "status": "created",
        "cityTo": payload.city_to,
        "weightKg": payload.weight_kg,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "duplicate": False,
    }
    SHIPMENTS[shipment["shipmentId"]] = shipment
    return shipment


@app.get("/api/v1/shipments/{shipment_id}")
def shipment_status(shipment_id: str, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check_key(x_api_key)
    _apply_rate_limit(x_api_key)
    shipment = SHIPMENTS.get(shipment_id)
    if not shipment:
        raise HTTPException(status_code=404, detail=f"заявка {shipment_id} не найдена")
    # Имитация жизненного цикла: created → in_transit → delivered
    order = ["created", "in_transit", "delivered"]
    index = order.index(shipment["status"])
    shipment["status"] = order[min(index + 1, len(order) - 1)]
    return shipment


@app.get("/api/v1/shipments/{shipment_id}/label")
async def shipment_label(
    shipment_id: str,
    x_api_key: Optional[str] = Header(default=None),
    x_fault_mode: Optional[str] = Header(default=None),
) -> dict:
    _check_key(x_api_key)
    _apply_rate_limit(x_api_key)
    await _apply_fault(x_fault_mode)
    if shipment_id not in SHIPMENTS:
        raise HTTPException(status_code=404, detail=f"заявка {shipment_id} не найдена")
    return {"shipmentId": shipment_id, "labelFormat": "pdf-stub",
            "url": f"https://mock.tk/labels/{shipment_id}.pdf"}
