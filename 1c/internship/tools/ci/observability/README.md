# Наблюдаемость стенда (спринт 46: task_271–276)

| Файл | Что делает |
|---|---|
| `prometheus.yml` | скрейп-конфиг: экспортёр RIH, RabbitMQ, PostgreSQL, nginx |
| `alert_rules.yml` | 6 алертов **по симптомам** с runbook-ссылками |
| `alertmanager.yml` | маршрутизация page/ticket, группировка, подавление, повтор через 4 ч |
| `grafana/dashboards/rih-slo.json` | дашборд SLO: доступность, error budget, p95/p99, ошибки, очереди, отставание обменов |
| `grafana/dashboards/datasources.yml` | Prometheus + PostgreSQL как источники |
| `grafana/dashboards/dashboards.yml` | provisioning: дашборды подхватываются автоматически |

## SLI → SLO → алерт

| SLI (что измеряем) | SLO (обещание) | Алерт (симптом) |
|---|---|---|
| `rih_up` | 99,5% времени за 30 дней | `RIHIntegrationDown` (page) |
| доля обращений с кодом 5xx/таймаут | < 20% за 5 минут по системе | `RIHPartnerUnavailable` (page) |
| p95 `rih_integration_duration_seconds` | ≤ 2 с | `RIHLatencySLOBreach` (ticket) |
| `rih_queue_depth{state="ready"}` | ≤ 500 сообщений | `RIHQueueBacklog` (page) |
| прирост DLQ | ≤ 10 за 15 минут | `RIHDeadLetterGrowing` (ticket) |
| `rih_exchange_lag_seconds` | ≤ 900 с | `RIHExchangeLag` (ticket) |

## Правила, которые здесь отрабатываются

1. **Алерт по симптому, а не по причине.** «PostgreSQL использует 90% памяти» —
   не алерт, если пользователь ничего не заметил. «Заказы не загружаются» — алерт.
2. **У каждого алерта есть runbook.** Путь в метке `runbook`; файл живёт в
   `../../docs/runbooks/` (создаётся в task_272).
3. **Error budget управляет скоростью релизов.** Сгорел бюджет → заморозка
   рискованных изменений, приоритет надёжности (task_271, task_276).
4. **Подавление дублей.** Один упавший сервис не должен породить двадцать
   уведомлений: `inhibit_rules` в Alertmanager.
5. **Дежурство — процесс, а не геройство.** Смена дежурного, шаблоны коммуникаций
   и журнал инцидентов описаны в task_273, task_274.

## Проверка без 1С

```bash
docker compose -f docker-compose.full.yml up -d prometheus alertmanager grafana metrics_exporter
curl -s http://localhost:9090/api/v1/rules | python3 -m json.tool | head -40
curl -s http://localhost:9090/api/v1/alerts
# Grafana: http://localhost:3000 (admin / GRAFANA_ADMIN_PASSWORD из .env) → дашборд "RIH · SLO интеграций"
```
