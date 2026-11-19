# Определения RabbitMQ

Стенд поднимается сразу с нужной топик-структурой, чтобы задание task_111
начиналось не с «придумать очереди», а с «объяснить, почему топология такая».

## Топология

- **`rih.commands`** (direct) — команды извне в 1С. Ключ `orders.in` → очередь `rih.orders.in`.
- **`rih.events`** (topic) — события из 1С наружу: `orders.*`, `stock.changed`,
  `prices.changed`, `loyalty.*`, `cdc.#`.
- **`rih.dlx`** (topic) — обменник мёртвых писем. Политика `rih-dlq` привязывает
  его ко всем очередям вида `rih.*.in|out`.

## Политики

| Политика | Паттерн | Смысл |
|---|---|---|
| `rih-dlq` | `^rih\..*\.(in\|out)$` | dead-letter в `rih.dlx`, TTL 24 ч, максимум 100 000 сообщений, при переполнении — `reject-publish` |
| `rih-dlq-retain` | `^rih\..*\.dlq$` | хранение DLQ 7 дней, при переполнении отбрасываем самые старые |

`reject-publish` выбран намеренно: лучше явная ошибка на стороне отправителя,
чем тихо потерянное сообщение. Альтернатива (`drop-head`) обсуждается в task_112
как решение с другой ценой — её надо записать в ADR.

## Проверка

```bash
docker compose exec rabbitmq rabbitmq-diagnostics -q ping
docker compose exec rabbitmq rabbitmqctl list_queues name messages consumers
docker compose exec rabbitmq rabbitmqctl list_policies
# веб-интерфейс: http://localhost:15672 (пользователь и пароль из .env)
```

## Отправка тестового сообщения

```bash
docker compose exec rabbitmq rabbitmqadmin publish \
  exchange=rih.commands routing_key=orders.in \
  payload='{"externalId":"SHOP-000001","correlationId":"test-001"}'
```

Если `rabbitmqadmin` недоступен, используйте консоль управления или
`src/scripts/seed_demo_data.py`.
