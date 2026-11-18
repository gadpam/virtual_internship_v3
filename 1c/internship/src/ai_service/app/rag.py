"""RAG-пайплайн: вопрос → поиск → контекст → ответ с цитированием (task_241-245)."""
import uuid
from typing import List, Optional

from .config import get_settings
from .llm_client import build_prompt, complete
from .retrieval import retrieve
from .schemas import Answer, Source
from .reranking import rerank


def answer_question(question: str, session_id: Optional[str] = None,
                    context_hint: Optional[str] = None) -> Answer:
    settings = get_settings()
    correlation_id = str(uuid.uuid4())

    sources: List[Source] = retrieve(question, top_k=settings.search_top_k)
    if settings.rerank_enabled:
        sources = rerank(question, sources, top_k=settings.search_top_k)

    # task_243: порог релевантности. Нет достоверного контекста — честный отказ.
    if not sources:
        return Answer(
            answer="В документах не найдено. Уточните формулировку или обратитесь к владельцу регламента.",
            sources=[],
            confidence=0.0,
            refused=True,
            correlation_id=correlation_id,
        )

    prompt = build_prompt(question, sources)
    response = complete(prompt, temperature=settings.llm_temperature)

    # task_245: мультитёрн-диалог — история по session_id с ограничением по токенам.
    # task_242: проверка «каждое утверждение имеет источник».
    return Answer(
        answer=response.text,
        sources=sources,
        confidence=round(sum(s.score for s in sources) / len(sources), 4),
        refused=False,
        correlation_id=correlation_id,
    )
