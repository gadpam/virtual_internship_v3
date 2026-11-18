# Контракт внешнего трекера задач (TRK) · task_174

Mock-сервис: `src/mock_tracker_api` · порт `8024` · через nginx `/tracker/`.
Авторизация: `X-Api-Key` (`MOCK_TRACKER_API_KEY`).

## Зачем RIH внешний трекер

Инциденты и задачи процессов живут там, где их видит не только разработчик:
дежурный, руководитель, смежная команда. RIH создаёт задачу и ведёт её статус,
а не хранит свой параллельный список (task_174).

## Методы

### `POST /api/v1/issues` — создание задачи

```json
{ "external_ref": "РИХ_Инцидент/2026-11-17-001", "title": "Лояльность недоступна",
  "description": "...", "priority": "high", "assignee": "dezhurnyy", "due_in_hours": 4 }
```

* `priority`: `low | medium | high | critical`;
* `external_ref` — ключ идемпотентности: повтор возвращает ту же задачу с
  `"duplicate": true`.

Ответ `201`: `issueId`, `externalRef`, `title`, `description`, `priority`,
`status` (`new`), `assignee`, `createdAt`, `dueAt`, `duplicate`.

### `GET /api/v1/issues` — список

Фильтры: `status`, `assignee`, `due_before`, `limit` (1…500).
Ответ: `{ "total": int, "items": [ Issue ] }`.

### `GET /api/v1/issues/{issue_id}` — карточка

Ответ: задача + `"comments": [ { "author", "text", "createdAt" } ]`.

### `PATCH /api/v1/issues/{issue_id}` — изменение

Поля: `status`, `assignee`, `due_at`. Переходы статуса ограничены:

| Из | Разрешено в |
|---|---|
| `new` | `in_progress`, `cancelled` |
| `in_progress` | `resolved`, `cancelled` |
| `resolved` | `closed`, `in_progress` |
| `closed` | — (только новая задача) |

Недопустимый переход → 422 с перечислением разрешённых. Это пример **валидации
состояния на стороне сервиса**: клиент не обязан знать матрицу переходов, но
обязан обработать 422.

### `POST /api/v1/issues/{issue_id}/comments` — комментарий

Тело: `{ "author": string, "text": string }`. Ответ `201`: комментарий с `createdAt`.
Комментарии — журнал разбора инцидента (task_274): таймлайн восстанавливается
по ним, а не по памяти.

### `GET /api/v1/sla` — нарушения SLA

Ответ: `{ "checkedAt", "total", "items": [ Issue + "overdueHours" ] }` — задачи,
срок которых истёк, а статус не `resolved`/`closed`, отсортированные по просрочке.

### `GET /health`

`{ "status": "ok", "service": "mock_tracker_api", "issues": int }`.

## Правила интеграции

1. **Создание задачи — асинхронно.** Сбой трекера не должен останавливать обмен:
   задача уходит в очередь и создаётся позже.
2. **`external_ref` обязателен** — по нему задача связывается с объектом 1С и не
   дублируется при повторе.
3. **Статусы синхронизируются в одну сторону** (1С → трекер). Обратная синхронизация
   появляется только вместе с обработкой конфликтов (task_255).
4. **Приоритет = критичность инцидента**, а не настроение автора: `critical` —
   остановлен обмен с магазином или банком.
