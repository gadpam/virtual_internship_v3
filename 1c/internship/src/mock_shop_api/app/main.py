"""Mock API онлайн-магазина: каталог, заказы, остатки + режимы сбоев.

Режимы сбоев нужны для заданий task_127-132 (таймауты, ретраи, circuit breaker,
компенсации, деградация) и task_140-143 (контрактные, интеграционные, нагрузочные тесты).
"""
import asyncio
import os
import random
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

API_KEY = os.getenv("MOCK_SHOP_API_KEY", "mock-shop-key")

app = FastAPI(title="Mock Online Shop API", version="1.0.0")

# --------------------------------------------------------------------------------------------------
# Модель данных (память процесса: перезапуск очищает состояние — это удобно для тестов)
# --------------------------------------------------------------------------------------------------


def _to_camel(name: str) -> str:
    """`external_id` -> `externalId`: единое правило именования полей в ответах (task_82)."""
    head, *tail = name.split("_")
    return head + "".join(word.capitalize() for word in tail)


class _CamelModel(BaseModel):
    """Запросы принимаем в snake_case (как присылает 1С), ответы отдаём в camelCase."""

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class Product(_CamelModel):
    external_id: str
    sku: str
    name: str
    group: str
    price: float
    currency: str = "BYN"
    changed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class OrderLine(_CamelModel):
    sku: str
    quantity: float = Field(..., gt=0)
    price: float = Field(..., ge=0)


class OrderIn(_CamelModel):
    external_id: str = Field(..., description="Идентификатор заказа на стороне магазина")
    customer_ref: Optional[str] = Field(None, description="Ссылка на клиента (маскируется в 1С)")
    lines: List[OrderLine] = Field(..., min_length=1, description="Хотя бы одна строка (контракт task_77)")
    created_at: Optional[datetime] = None


class OrderState(_CamelModel):
    external_id: str
    status: str = "new"
    total: float = 0.0
    lines: List[OrderLine] = Field(default_factory=list)
    received_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: Optional[str] = None


PRODUCTS: Dict[str, Product] = {}
ORDERS: Dict[str, OrderState] = {}


def _seed_products(count: int = 50) -> None:
    if PRODUCTS:
        return
    now = datetime.now(timezone.utc)
    for index in range(count):
        sku = f"SKU-{index:05d}"
        PRODUCTS[sku] = Product(
            external_id=f"ext-{index:05d}",
            sku=sku,
            name=f"Товар учебный {index}",
            group="Учебные товары" if index % 2 else "Сопутствующие",
            price=round(random.uniform(2.0, 500.0), 2),
            changed_at=now - timedelta(days=index % 30),
        )


_seed_products()


# --------------------------------------------------------------------------------------------------
# Режимы сбоев
# --------------------------------------------------------------------------------------------------


async def apply_fault(fault: Optional[str], header_fault: Optional[str]) -> None:
    mode = (header_fault or fault or "").lower().strip()
    if not mode or mode == "ok":
        return
    if mode == "error500":
        raise HTTPException(status_code=500, detail="mock: внутренняя ошибка магазина")
    if mode == "timeout":
        await asyncio.sleep(35)  # больше типового таймаута клиента (task_127)
        return
    if mode == "slow":
        await asyncio.sleep(4)
        return
    if mode == "flaky":
        # task_78: случайные сбои с заданной вероятностью (MOCK_FLAKY_P, по умолчанию 0.5)
        if random.random() < float(os.getenv("MOCK_FLAKY_P", "0.5")):
            raise HTTPException(status_code=500, detail="mock: случайный сбой (flaky)")
        return
    if mode.startswith("delay:"):
        # task_78: настраиваемая задержка, например X-Fault-Mode: delay:1200 (мс, потолок 30 с)
        try:
            delay_ms = min(int(mode.split(":", 1)[1]), 30000)
        except ValueError:
            raise HTTPException(status_code=400, detail="mock: задержка задаётся числом миллисекунд")
        await asyncio.sleep(delay_ms / 1000)
        return
    if mode == "rate429":
        raise HTTPException(
            status_code=429,
            detail="mock: превышен лимит запросов",
            headers={"Retry-After": "5"},
        )
    if mode == "garbage":
        # Намеренно ломаем контракт: ответ не соответствует схеме (task_140).
        raise HTTPException(status_code=200, detail="not-json-payload-{[[")
    if mode == "duplicate":
        return  # обрабатывается в POST /orders: повторяет external_id с другим ключом
    raise HTTPException(status_code=400, detail=f"mock: неизвестный режим сбоя '{mode}'")


def check_api_key(x_api_key: Optional[str] = Header(default=None)) -> str:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="не указан X-Api-Key")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="неверный X-Api-Key")
    return x_api_key


# --------------------------------------------------------------------------------------------------
# Маршруты
# --------------------------------------------------------------------------------------------------


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock_shop_api", "products": len(PRODUCTS), "orders": len(ORDERS)}


@app.get("/api/v1/products")
async def get_products(
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    changed_since: Optional[datetime] = None,
    fault: Optional[str] = None,
    x_fault_mode: Optional[str] = Header(default=None),
    _key: str = Depends(check_api_key),
) -> dict:
    await apply_fault(fault, x_fault_mode)
    items = list(PRODUCTS.values())
    if changed_since:
        items = [p for p in items if p.changed_at >= changed_since]
    page = items[offset: offset + limit]
    return {
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "items": [p.model_dump(mode="json", by_alias=True) for p in page],
    }


@app.put("/api/v1/products")
async def put_products(
    payload: List[Product],
    fault: Optional[str] = None,
    x_fault_mode: Optional[str] = Header(default=None),
    _key: str = Depends(check_api_key),
) -> dict:
    """Приём выгрузки каталога и цен из 1С (task_91). Поддерживает частичный успех."""
    await apply_fault(fault, x_fault_mode)
    accepted, rejected = 0, []
    for item in payload:
        if item.price < 0:
            rejected.append({"sku": item.sku, "reason": "отрицательная цена"})
            continue
        PRODUCTS[item.sku] = item
        accepted += 1
    return {"accepted": accepted, "rejected": rejected}


@app.post("/api/v1/orders", status_code=201)
async def create_order(
    payload: OrderIn,
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
    fault: Optional[str] = None,
    x_fault_mode: Optional[str] = Header(default=None),
    _key: str = Depends(check_api_key),
) -> dict:
    await apply_fault(fault, x_fault_mode)
    total = round(sum(line.quantity * line.price for line in payload.lines), 2)
    existing = ORDERS.get(payload.external_id)

    if existing:
        # task_105: идемпотентность. Тот же external_id + тот же ключ → тот же результат.
        if idempotency_key and existing.idempotency_key == idempotency_key:
            return {"externalId": existing.external_id, "status": existing.status,
                    "total": existing.total, "duplicate": True}
        raise HTTPException(status_code=409, detail=f"заказ {payload.external_id} уже существует")

    order = OrderState(
        external_id=payload.external_id,
        total=total,
        lines=payload.lines,
        idempotency_key=idempotency_key,
        received_at=payload.created_at or datetime.now(timezone.utc),
    )
    ORDERS[order.external_id] = order
    return {"externalId": order.external_id, "status": order.status, "total": order.total, "duplicate": False}


@app.get("/api/v1/orders")
async def list_orders(
    status: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    _key: str = Depends(check_api_key),
) -> dict:
    items = list(ORDERS.values())
    if status:
        items = [o for o in items if o.status == status]
    return {"total": len(items),
            "items": [o.model_dump(mode="json", by_alias=True) for o in items[:limit]]}


@app.patch("/api/v1/orders/{external_id}/status")
async def change_status(
    external_id: str,
    status: str = Query(..., description="new|reserved|shipped|delivered|cancelled"),
    fault: Optional[str] = None,
    x_fault_mode: Optional[str] = Header(default=None),
    _key: str = Depends(check_api_key),
) -> dict:
    await apply_fault(fault, x_fault_mode)
    order = ORDERS.get(external_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"заказ {external_id} не найден")
    order.status = status
    return {"externalId": order.external_id, "status": order.status}


@app.get("/api/v1/stock")
async def stock(
    warehouse: Optional[str] = None,
    fault: Optional[str] = None,
    x_fault_mode: Optional[str] = Header(default=None),
    _key: str = Depends(check_api_key),
) -> dict:
    """Остатки, которые магазин ожидает получить из 1С (проверка выгрузки task_91)."""
    await apply_fault(fault, x_fault_mode)
    started = time.perf_counter()
    rows = [
        {"sku": sku, "warehouse": warehouse or "РЦ-Минск", "quantity": round(random.uniform(0, 200), 2)}
        for sku in list(PRODUCTS)[:200]
    ]
    return {"took_ms": int((time.perf_counter() - started) * 1000), "items": rows}
