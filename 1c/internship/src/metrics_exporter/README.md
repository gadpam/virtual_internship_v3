# Экспортёр метрик (Prometheus)

Собирает метрики учебного стенда в формате Prometheus и отдаёт их на
`GET /metrics`. Метрики нужны в заданиях task_114 (p95/p99 интеграций),
task_271–272 (SLI/SLO, алерты), task_196 (мониторинг кластера), task_202 (capacity planning).

Сам экспортэр не «измеряет» 1С напрямую: 1С отдаёт данные в JSON по своему
HTTP-сервису `РИХ_Метрики`, экспортёр преобразует их в текст Prometheus.
Это честная схема — именно так обычно и делают, потому что 1С не умеет
протокол Prometheus из коробки.

## Запуск

```bash
cd 1c/internship/src/metrics_exporter
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8025
curl -s http://localhost:8025/metrics | head -30
```

## Метрики

| Метрика | Тип | Метки |
|---|---|---|
| `rih_integration_requests_total` | counter | `system`, `operation`, `status` |
| `rih_integration_duration_seconds` | histogram | `system`, `operation` |
| `rih_queue_depth` | gauge | `queue`, `state` |
| `rih_errors_total` | counter | `system`, `code` |
| `rih_up` | gauge | `service` |
| `rih_exchange_lag_seconds` | gauge | `plan`, `direction` |

## Формат histogram

Экспортёр пересчитывает сырые значения в бакеты `le` (0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, +Inf),
чтобы PromQL мог посчитать `histogram_quantile(0.95, ...)`. Именно из этой величины
строится SLO «95% интеграций быстрее 2 секунд» в task_271.

## Если 1С недоступна

Экспортёр не падает: он отдаёт `rih_up{service="rih_1c"} 0`, добавляет в начало
текста строку `# WARNING: источник метрик недоступен…` и повторяет последний
успешный снимок. Отсутствие метрик — тоже сигнал: на `rih_up == 0` и на «экспортёр
молчит» (цель `absent(rih_up)`) строятся алерты в task_272.
