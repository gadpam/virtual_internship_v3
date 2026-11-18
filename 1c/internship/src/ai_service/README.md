# AI-сервис RIH (FastAPI) — заготовка под sprint_40–42

Сервис RAG-ассистента для внутренних регламентов и инструкций холдинга.
Вы пишете его в заданиях task_235 … task_252. Стартовый код запускается и отвечает
на `/health`, чтобы интеграцию с 1С можно было отлаживать с самого начала.

## Быстрый старт

```bash
cd 1c/internship/src/ai_service
python3 -m venv .venv && source .venv/bin/activate     # task_229
pip install -r requirements.txt
cp .env.example .env                                    # ключи — только сюда, не в Git
uvicorn app.main:app --host 0.0.0.0 --port 8010 --reload
# документация: http://localhost:8010/docs
pytest -q                                               # task_232
```

## Состав

```
app/
├── main.py           — приложение FastAPI, единый формат ошибок, correlationId
├── routes.py         — маршруты: /health, /api/v1/search, /api/v1/ask, /api/v1/stats
├── schemas.py        — Pydantic-модели запросов и ответов (контракт)
├── config.py         — настройки из окружения (модель, лимиты, бюджет)
├── chunking.py       — корпус знаний и чанкование (task_236)
├── embeddings.py     — получение эмбеддингов + кеш (task_235, task_240)
├── vectorstore.py    — векторный индекс: pgvector или FAISS (task_237)
├── retrieval.py      — поиск top-K, фильтры, гибридный поиск (task_238, task_239)
├── reranking.py      — переранжирование выдачи (task_245)
├── rag.py            — пайплайн вопрос → контекст → ответ LLM (task_241)
└── llm_client.py     — вызов LLM API: таймауты, ретраи, лимиты, стоимость
tests/                — pytest: контракт, поиск, отказ при низкой релевантности
evaluation/           — эталонные вопросы, метрики hit@k / MRR, отчёты (task_238, task_244)
```

## Контракт

Описан в `1c/internship/docs/api/ai_assistant.yaml` (создаётся в task_242)
и в Pydantic-моделях `app/schemas.py`. Единый формат ошибок совпадает с HTTP-сервисами
1С (task_82): `code`, `message`, `details`, `incidentId`, `timestamp`.

## Что реализовано в заготовке, а что пишете вы

| Файл | Состояние | Задание |
|---|---|---|
| main.py, routes.py, schemas.py, config.py | работает (health, stats, заглушки search/ask) | task_231 |
| chunking.py, embeddings.py, vectorstore.py | заглушки с интерфейсом | task_235–237 |
| retrieval.py, reranking.py, rag.py | заглушки (возвращают «не реализовано») | task_238–245 |
| llm_client.py | интерфейс + имитация без ключа | task_241 |
| evaluation/ | шаблоны эталонов и метрик | task_238, task_244 |

## Правила работы с ключами и данными

- Ключ LLM-провайдера — только в `.env` (в `.gitignore`), никогда в коде (task_134).
- Не отправляйте персональные данные во внешнее LLM API: маскирование и минимизация
  описаны в task_135 и task_291.
- Ставьте лимиты стоимости и количества запросов (task_240, task_249).
