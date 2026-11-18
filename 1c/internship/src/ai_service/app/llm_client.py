"""Клиент LLM-провайдера (task_241).

Без ключа работает имитация: она честно помечает ответ как mock, чтобы вы не приняли
её за настоящую генерацию. Реальный вызов подключается в task_241 с таймаутом,
ретраями (практики task_127-129) и учётом стоимости (task_240).
"""
import os
import time
from dataclasses import dataclass
from typing import List, Optional

from .config import get_settings
from .schemas import Source


@dataclass
class LlmResponse:
    text: str
    provider: str
    model: Optional[str]
    latency_ms: int
    prompt_chars: int
    completion_chars: int
    estimated_cost_usd: float = 0.0


SYSTEM_PROMPT = (
    "Ты — ассистент по внутренним регламентам и инструкциям компании. "
    "Отвечай ТОЛЬКО на основе предоставленных фрагментов. "
    "Каждое утверждение сопровождай ссылкой на источник в формате [1], [2]. "
    "Если в фрагментах нет ответа, напиши: «В документах не найдено» и не выдумывай. "
    "Не используй знания вне предоставленного контекста."
)


def build_prompt(question: str, sources: List[Source]) -> str:
    """Собирает промпт: системные правила + пронумерованные фрагменты + вопрос."""
    context_parts = []
    for index, source in enumerate(sources, start=1):
        header = f"[{index}] {source.section or source.document} (версия {source.version})"
        context_parts.append(f"{header}\n{source.text}")
    context = "\n\n---\n\n".join(context_parts) if context_parts else "(фрагменты не найдены)"
    return f"{SYSTEM_PROMPT}\n\nФРАГМЕНТЫ:\n{context}\n\nВОПРОС: {question}\n\nОТВЕТ:"


def complete(prompt: str, temperature: Optional[float] = None) -> LlmResponse:
    settings = get_settings()
    started = time.perf_counter()

    if settings.llm_provider == "mock" or not os.getenv("LLM_API_KEY", settings.llm_api_key):
        text = (
            "MOCK-ОТВЕТ: подключите LLM-провайдер в .env (задание task_241). "
            "Промпт сформирован, фрагменты переданы, генерация не выполнялась."
        )
        provider = "mock"
        model = None
    else:
        # task_241: реальный вызов HTTP LLM API.
        # Обязательные требования: таймаут (task_127), ретраи с джиттером (task_128),
        # circuit breaker (task_129), учёт токенов и стоимости (task_240),
        # маскирование ПДн до отправки (task_135, task_291).
        raise NotImplementedError("Реальный LLM-вызов реализуется в задании task_241")

    return LlmResponse(
        text=text,
        provider=provider,
        model=model,
        latency_ms=int((time.perf_counter() - started) * 1000),
        prompt_chars=len(prompt),
        completion_chars=len(text),
    )
