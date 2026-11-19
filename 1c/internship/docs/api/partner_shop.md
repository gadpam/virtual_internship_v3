# Контракт онлайн-магазина (SHOP) · task_91, task_83

Mock-сервис: `src/mock_shop_api` · порт `8020` · через nginx `/shop/` · порт 8080.
Авторизация: заголовок `X-Api-Key` (значение из `.env`: `MOCK_SHOP_API_KEY`).

## Общие соглашения

* запросы — `application/json`, поля в **snake_case**;
* ответы — `application/json`, поля в **camelCase** (единое правило, task_82);
* даты — ISO 8601 в UTC;
* ошибки — единый формат (`error_format.md`);
* сбои для тестов — заголовок `X-Fault-Mode` или параметр `fault`.

## Методы

### `GET /api/v1/products` — каталог

| Параметр | Тип | Обяз. | Описание |
|---|---|---|---|
| `limit` | int (1…1000) | нет | размер страницы, по умолчанию 50 |
| `offset` | int ≥ 0 | нет | смещение |
| `changed_since` | datetime | нет | только товары, изменённые с момента (инкрементальная выгрузка) |

Ответ: `{ "total": int, "limit": int, "offset": int, "items": [ Product ] }`

**Product:** `externalId`, `sku`, `name`, `group`, `price`, `currency`, `changedAt`.

### `PUT /api/v1/products` — приём выгрузки каталога из 1С

Тело: массив `Product` (поля в snake_case: `external_id`, `sku`, `name`, `group`,
`price`, `currency`, `changed_at`).

Ответ: `{ "accepted": int, "rejected": [ { "sku": string, "reason": string } ] }`

**Частичный успех — норма.** Товар с отрицательной ценой отклоняется, остальные
принимаются. Клиент обязан обработать `rejected`, а не считать выгрузку успешной
по коду 200 (task_91).

### `POST /api/v1/orders` — создание заказа

Заголовок `Idempotency-Key` (UUID) — обязателен для повторов.

```json
{
  "external_id": "SHOP-1042",
  "customer_ref": "CL-77",
  "lines": [{ "sku": "SKU-00001", "quantity": 2, "price": 12.5 }],
  "created_at": "2026-11-17T09:10:00Z"
}
```

Ответ `201`: `{ "externalId": "SHOP-1042", "status": "new", "total": 25.0, "duplicate": false }`

Поведение при повторе (task_105):

| Условие | Ответ |
|---|---|
| тот же `external_id` + тот же `Idempotency-Key` | 200/201, `duplicate: true`, тот же результат |
| тот же `external_id`, другой ключ или без ключа | 409 `CONFLICT` |

`total` считается на стороне магазина как сумма `quantity × price` по строкам с округлением до
копейки. Клиент сверяет его со своей суммой и при расхождении не проводит документ.

### `GET /api/v1/orders` — список заказов

Параметры: `status` (`new|reserved|shipped|delivered|cancelled`), `limit` (1…1000).
Ответ: `{ "total": int, "items": [ OrderState ] }`, где **OrderState** —
`externalId`, `status`, `total`, `lines[]`, `receivedAt`, `idempotencyKey`.

### `PATCH /api/v1/orders/{external_id}/status` — смена статуса

Параметр `status` (query, обязательный). Ответ: `{ "externalId": ..., "status": ... }`.
Неизвестный `external_id` → 404 `NOT_FOUND`.

### `GET /api/v1/stock` — остатки

Параметр `warehouse` (по умолчанию `РЦ-Минск`).
Ответ: `{ "took_ms": int, "items": [ { "sku", "warehouse", "quantity" } ] }` —
не более 200 позиций за вызов. `took_ms` нужен для замеров (task_143).

### `GET /health` — живость

Ответ: `{ "status": "ok", "service": "mock_shop_api", "products": int, "orders": int }`.
Без авторизации — используется healthcheck контейнера и nginx.

## Режимы сбоев

`X-Fault-Mode` (или `?fault=`): `ok`, `error500`, `timeout` (35 с), `slow` (4 с),
`rate429` (+`Retry-After: 5`), `garbage` (ответ не соответствует схеме),
`duplicate` (повтор `external_id`). Матрица — `tests/fixtures/faults_matrix.json`.

## Лимиты и таймауты клиента

| Параметр | Значение | Обоснование |
|---|---|---|
| таймаут соединения | 5 с | nginx отдаёт 502 раньше (task_127) |
| таймаут чтения | 30 с | меньше `timeout`-режима mock, чтобы успеть отреагировать |
| повторов | 3 | дальше — DLQ и инцидент |
| задержка повтора | `min(2^n, 30)` с + джиттер | task_128 |
| объём выгрузки каталога | ≤ 1000 позиций за вызов | страница `limit` |

## Журнал и трассировка

Каждый вызов пишется в `РИХ_ЖурналИнтеграций` с `correlationId` (= `Idempotency-Key`
для заказов, иначе UUID вызова). Найти вызов: `docs/api/error_format.md` → `incidentId`.
