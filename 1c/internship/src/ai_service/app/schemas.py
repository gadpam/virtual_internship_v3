"""Pydantic-модели контракта (task_231, task_242).

Контракт должен совпадать с 1С-стороной: общий модуль РИХ_AIКлиент (task_233)
и OpenAPI-описание internship/docs/api/ai_assistant.yaml (task_242).
"""
from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Source(BaseModel):
    """Источник ответа: документ, раздел, версия, релевантный фрагмент (task_242)."""

    document: str = Field(..., description="Идентификатор или путь документа корпуса")
    section: Optional[str] = Field(None, description="Раздел/заголовок документа")
    version: Optional[str] = Field(None, description="Версия документа (важно для аудита)")
    chunk_id: str = Field(..., description="Идентификатор фрагмента в индексе")
    text: str = Field(..., description="Фрагмент, на котором основан ответ")
    score: float = Field(..., ge=0.0, le=1.0, description="Оценка релевантности")


class Answer(BaseModel):
    """Ответ ассистента с цитированием источников."""

    answer: str
    sources: List[Source] = Field(default_factory=list)
    confidence: float = Field(..., ge=0.0, le=1.0)
    refused: bool = Field(
        False,
        description="True, если данных в корпусе не найдено и ассистент отказался отвечать (task_243)",
    )
    correlation_id: Optional[str] = None


class SearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000)
    top_k: int = Field(5, ge=1, le=50)
    filters: dict = Field(default_factory=dict, description="Фильтры по метаданным (task_237)")


class SearchResponse(BaseModel):
    results: List[Source] = Field(default_factory=list)
    took_ms: int = 0
    correlation_id: Optional[str] = None


class AskRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=4000)
    session_id: Optional[str] = Field(None, description="Идентификатор диалога (task_245)")
    context_hint: Optional[str] = Field(
        None,
        description="Контекст из 1С: тип объекта, ситуация. БЕЗ персональных данных (task_248)",
    )


class StatsResponse(BaseModel):
    service: str
    version: str
    index_vectors: int = 0
    index_documents: int = 0
    corpus_version: Optional[str] = None
    embedding_model: Optional[str] = None
    requests_total: int = 0
    requests_refused: int = 0
    avg_latency_ms: float = 0.0
    estimated_cost_usd_month: float = 0.0


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[str] = None
    incident_id: str
    timestamp: datetime = Field(default_factory=utcnow)
