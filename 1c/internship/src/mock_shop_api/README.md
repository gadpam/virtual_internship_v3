# Mock-сервис «Онлайн-магазин» (внешний партнёр)

Имитирует API онлайн-магазина: каталог, заказы, статусы. Нужен, чтобы стенд был
стабильным: реальный партнёр доступен не всегда, а ваш код должен быть проверен.

Используется в заданиях: task_74, task_76, task_78, task_91, task_114, task_128,
task_132, task_141, task_143.

## Запуск

```bash
cd 1c/internship/src/mock_shop_api
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8020 --reload
# документация: http://localhost:8020/docs
```

Или в контейнере: `docker compose -f ../../tools/docker-compose.yml up -d mock_shop_api`.

## Режимы сбоев (для отладки надёжности)

Передаются заголовком `X-Fault-Mode` или query-параметром `fault`:

| Режим | Поведение | Где используется |
|---|---|---|
| `ok` | обычный ответ | базовые тесты |
| `error500` | внутренняя ошибка | ретраи (task_128), компенсации (task_130) |
| `timeout` | задержка > таймаута клиента | таймауты (task_127), circuit breaker (task_129) |
| `slow` | задержка 3–5 с | деградация (task_131), p95 метрики (task_114) |
| `rate429` | 429 + Retry-After | rate limiting (task_93) |
| `garbage` | невалидный JSON/схема | контрактные тесты (task_140), валидация (task_75) |
| `duplicate` | тот же заказ под другим messageId | идемпотентность (task_105) |

Пример: `curl -H "X-Fault-Mode: error500" http://localhost:8020/api/v1/orders/1`.

## Эндпоинты

- `GET /health` — статус
- `GET /api/v1/products` — каталог (пагинация `limit`/`offset`, фильтр `changed_since`)
- `PUT /api/v1/products` — приём выгрузки каталога и цен из 1С (task_91)
- `POST /api/v1/orders` — создание заказа (idempotency по `externalId`)
- `GET /api/v1/orders` — список заказов для выгрузки в 1С
- `PATCH /api/v1/orders/{id}/status` — изменение статуса
- `GET /api/v1/stock` — остатки, которые магазин ожидает от 1С

## Авторизация

Заголовок `X-Api-Key` (значение из `.env`, по умолчанию `mock-shop-key`).
Без ключа — 401, с неверным — 403. Проверяется в task_81 и task_133.
