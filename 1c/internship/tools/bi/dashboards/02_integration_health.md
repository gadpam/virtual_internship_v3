# Дашборд «Здоровье интеграций»

**Зритель:** дежурный инженер RIH, владелец интеграции, руководитель разработки.
**Вопрос:** обмениваются ли системы, укладываемся ли в SLO, где копятся очереди и
инциденты.
**Источники:** `marts.v_sli_integration`, `marts.fact_integration`,
`staging.exchange_status`, `staging.incidents`; параллельно те же SLI живые —
в Prometheus/Grafana (`tools/ci/observability/`).

## Панели

| № | Панель | Тип | Формула | Порог |
|---|---|---|---|---|
| 0 | Свежесть данных | Text | `marts.v_freshness` по `fact_integration` | 15 минут |
| 1 | Доступность за 30 дней | Big Number | M-005, среднее по системам | SLO 99,5% |
| 2 | Error budget | Bar gauge | `(1 - (1 - availability) / 0.005) * 100` | зелёный > 60% |
| 3 | p95 по системам | Time-series | M-006 | SLO 2 с |
| 4 | p99 по системам | Time-series | M-006 (0.99) | 5 с |
| 5 | Доля ошибок по кодам | Stacked bar | `requests_failed / requests_total` по `error_code` | 20% — алерт |
| 6 | Отставание обменов | Table | M-007 `EXTRACT(EPOCH FROM now() - last_success_at)` | 900 с |
| 7 | Инциденты по критичности | Time-series (столбцы) | M-008 `COUNT(*)` по `severity` | — |
| 8 | Топ операций по длительности | Table | `AVG(duration_ms)` по `system_code, operation` | — |
| 9 | Повторы и дубли | Big Number | `retries_total`, `duplicates` | дубли > 1% — разбор |

## Связь с алертами

Каждая панель с порогом соответствует алерту из `tools/ci/observability/alert_rules.yml`:

| Панель | Алерт |
|---|---|
| 1, 2 | `RIHIntegrationDown`, `RIHPartnerUnavailable` |
| 3 | `RIHLatencySLOBreach` |
| 5 | `RIHPartnerUnavailable` |
| 6 | `RIHExchangeLag` |
| 7 | `RIHDeadLetterGrowing` (косвенно) |

Расхождение порогов между дашбордом и алертом — дефект: дежурный видит «зелёный»
дашборд и одновременно получает page-уведомление. Порог живёт в одном месте.

## Drill-down

Клик по системе (панель 3) → фильтр по `system_code`; далее клик по операции
(панель 8) → список обращений с `correlation_id`, который дежурный вставляет в
поиск журнала 1С. Это и есть сквозная трассировка (task_274).

## Проверка приёмки

1. Цифры дашборда за последние сутки совпадают с Grafana в пределах погрешности
   выгрузки (не более 1%). Расхождение больше — проверяем конвейер, а не «сглаживаем».
2. Панель 6 показывает нарушение SLA на учебном обмене с задержкой 3 часа.
3. Дашборд открывается за ≤ 3 секунды.
