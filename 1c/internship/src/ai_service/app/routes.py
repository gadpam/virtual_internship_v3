"""Маршруты сервиса. Заготовки помечены заданиями, в которых их нужно реализовать."""
import time
from typing import List

from fastapi import APIRouter, HTTPException

from .config import get_settings
from .schemas import (
    Answer,
    AskRequest,
    SearchRequest,
    SearchResponse,
    Source,
    StatsResponse,
)

router = APIRouter()
settings = get_settings()

# Простейшая телеметрия (task_250 заменит на метрики в СУБД/Prometheus).
_stats = {"requests": 0, "refused": 0, "latency_ms": 0.0, "started": time.time()}


def observe_request(took_ms: int) -> None:
    _stats["requests"] += 1
    _stats["latency_ms"] = (_stats["latency_ms"] * (_stats["requests"] - 1) + took_ms) / _stats["requests"]


@router.get("/health")
def health() -> dict:
    """Проверка доступности: используется 1С-клиентом РИХ_AIКлиент (task_233)."""
    return {
        "status": "ok",
        "service": settings.service_name,
        "version": settings.service_version,
        "llm_provider": settings.llm_provider,
        "vector_backend": settings.vector_backend,
    }


@router.get("/api/v1/stats", response_model=StatsResponse)
def stats() -> StatsResponse:
    """Статистика сервиса (задание task_231: расширить показателями индекса и стоимости)."""
    from .vectorstore import get_store

    store = get_store()
    return StatsResponse(
        service=settings.service_name,
        version=settings.service_version,
        index_vectors=store.count(),
        index_documents=store.documents_count(),
        corpus_version=store.corpus_version(),
        embedding_model=settings.embedding_provider,
        requests_total=_stats["requests"],
        requests_refused=_stats["refused"],
        avg_latency_ms=round(_stats["latency_ms"], 1),
        estimated_cost_usd_month=0.0,  # task_240: расчёт стоимости по токенам
    )


@router.post("/api/v1/search", response_model=SearchResponse)
def search(payload: SearchRequest) -> SearchResponse:
    """Векторный поиск по корпусу (реализуется в task_237-239)."""
    started = time.perf_counter()
    from .retrieval import retrieve

    results: List[Source] = retrieve(payload.query, top_k=payload.top_k, filters=payload.filters)
    took_ms = int((time.perf_counter() - started) * 1000)
    return SearchResponse(results=results, took_ms=took_ms)


@router.post("/api/v1/ask", response_model=Answer)
def ask(payload: AskRequest) -> Answer:
    """RAG-ответ с цитированием источников (реализуется в task_241-245)."""
    from .rag import answer_question

    result = answer_question(payload.question, session_id=payload.session_id, context_hint=payload.context_hint)
    if result.refused:
        _stats["refused"] += 1
    return result


@router.post("/api/v1/index/rebuild")
def rebuild_index(full: bool = True) -> dict:
    """Перестроение индекса: полное или инкрементальное (task_240)."""
    from .vectorstore import get_store

    store = get_store()
    stats = store.rebuild(full=full)
    return {"status": "ok", "mode": "full" if full else "incremental", **stats}


def not_implemented(feature: str) -> HTTPException:
    """Общая заглушка: честная ошибка вместо правдоподобного вымысла."""
    return HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": f"{feature} ещё не реализован",
            "details": "См. соответствующее задание стажировки в YourTask.txt",
        },
    )
