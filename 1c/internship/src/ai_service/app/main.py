"""Приложение FastAPI: единый формат ошибок, correlationId, метрики (task_231, task_234)."""
import time
import uuid
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from .config import get_settings
from . import routes

settings = get_settings()

app = FastAPI(
    title="RIH AI Service",
    version=settings.service_version,
    description=(
        "RAG-ассистент по регламентам и инструкциям холдинга. "
        "Учебный проект виртуальной стажировки 1С (sprint_40-42)."
    ),
)

app.include_router(routes.router)


@app.middleware("http")
async def correlation_and_timing(request: Request, call_next: Callable) -> JSONResponse:
    """Сквозной корреляционный идентификатор и замер длительности (task_234, task_250)."""
    correlation_id = request.headers.get(settings.correlation_header) or str(uuid.uuid4())
    started = time.perf_counter()

    response = await call_next(request)

    took_ms = int((time.perf_counter() - started) * 1000)
    response.headers[settings.correlation_header] = correlation_id
    response.headers["X-Took-Ms"] = str(took_ms)
    routes.observe_request(took_ms)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Единый формат ошибки — такой же, как у HTTP-сервисов 1С (task_82, task_231)."""
    incident_id = str(uuid.uuid4())
    # task_234: полный стек пишем в лог сервиса, клиенту отдаём короткий текст.
    app.logger.exception("unhandled error", extra={"incident_id": incident_id}) if hasattr(app, "logger") else None
    return JSONResponse(
        status_code=500,
        content={
            "code": "INTERNAL_ERROR",
            "message": "Внутренняя ошибка AI-сервиса",
            "details": "Обратитесь к администратору, сообщите incidentId",
            "incidentId": incident_id,
            "path": request.url.path,
        },
        headers={settings.correlation_header: request.headers.get(settings.correlation_header, "")},
    )
