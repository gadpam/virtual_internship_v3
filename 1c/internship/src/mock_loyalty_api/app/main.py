"""Mock API программы лояльности (task_92, task_105, task_130).

Ключевая особенность — идемпотентность по operationId и поддержка сторно.
Состояние в памяти процесса: перезапуск контейнера очищает данные (удобно для тестов).
"""
import os
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

API_KEY = os.getenv("MOCK_LOYALTY_API_KEY", "mock-loyalty-key")

app = FastAPI(title="Mock Loyalty API", version="1.0.0")


class CardState(BaseModel):
    card: str
    balance: float = 0.0
    operations: List[dict] = Field(default_factory=list)


class Operation(BaseModel):
    operation_id: str = Field(..., description="Ключ идемпотентности (task_92)")
    card: str
    points: float = Field(..., gt=0)
    reason: Optional[str] = None
    occurred_at: Optional[datetime] = None


CARDS: Dict[str, CardState] = {}
OPERATIONS: Dict[str, dict] = {}
REVERSED: Dict[str, str] = {}


def _card(card: str) -> CardState:
    if card not in CARDS:
        CARDS[card] = CardState(card=card, balance=100.0)
    return CARDS[card]


def _check_key(x_api_key: Optional[str]) -> None:
    if not x_api_key:
        raise HTTPException(status_code=401, detail="не указан X-Api-Key")
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="неверный X-Api-Key")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "mock_loyalty_api", "cards": len(CARDS)}


@app.get("/api/v1/cards/{card}/balance")
def balance(card: str, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check_key(x_api_key)
    state = _card(card)
    return {"card": state.card, "balance": state.balance, "operations": state.operations[-50:]}


@app.post("/api/v1/accrue")
def accrue(payload: Operation, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check_key(x_api_key)
    state = _card(payload.card)

    if payload.operation_id in OPERATIONS:
        previous = OPERATIONS[payload.operation_id]
        return {**previous, "duplicate": True}

    record = {
        "operationId": payload.operation_id,
        "card": payload.card,
        "type": "accrue",
        "points": payload.points,
        "reason": payload.reason,
        "occurredAt": (payload.occurred_at or datetime.now(timezone.utc)).isoformat(),
        "duplicate": False,
    }
    state.balance = round(state.balance + payload.points, 2)
    state.operations.append(record)
    OPERATIONS[payload.operation_id] = record
    return {**record, "balance": state.balance}


@app.post("/api/v1/redeem")
def redeem(payload: Operation, x_api_key: Optional[str] = Header(default=None)) -> dict:
    _check_key(x_api_key)
    state = _card(payload.card)

    if payload.operation_id in OPERATIONS:
        return {**OPERATIONS[payload.operation_id], "duplicate": True}
    if state.balance < payload.points:
        raise HTTPException(status_code=422, detail="недостаточно баллов на карте")

    record = {
        "operationId": payload.operation_id,
        "card": payload.card,
        "type": "redeem",
        "points": payload.points,
        "reason": payload.reason,
        "occurredAt": (payload.occurred_at or datetime.now(timezone.utc)).isoformat(),
        "duplicate": False,
    }
    state.balance = round(state.balance - payload.points, 2)
    state.operations.append(record)
    OPERATIONS[payload.operation_id] = record
    return {**record, "balance": state.balance}


@app.post("/api/v1/reverse")
def reverse(operation_id: str, x_api_key: Optional[str] = Header(default=None)) -> dict:
    """Сторно операции (возврат чека). Идемпотентно-строгое: дважды не выполняется."""
    _check_key(x_api_key)
    original = OPERATIONS.get(operation_id)
    if not original:
        raise HTTPException(status_code=404, detail=f"операция {operation_id} не найдена")
    if operation_id in REVERSED:
        raise HTTPException(status_code=409, detail=f"операция {operation_id} уже сторнирована")

    state = _card(original["card"])
    sign = -1 if original["type"] == "accrue" else 1
    state.balance = round(state.balance + sign * original["points"], 2)
    REVERSED[operation_id] = datetime.now(timezone.utc).isoformat()
    state.operations.append({"operationId": f"reverse-{operation_id}", "type": "reverse",
                             "points": original["points"], "balance": state.balance})
    return {"status": "reversed", "operationId": operation_id, "balance": state.balance}
