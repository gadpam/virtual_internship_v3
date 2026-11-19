# Инструменты стенда

Всё, что поднимает учебный стенд RIH целиком или частично, и всё, что используется
в CI. Ни один файл здесь не содержит секретов — значения берутся из `.env`
(шаблон: `.env.example`), который в Git не попадает.

## Состав

| Путь | Что это | Задания |
|---|---|---|
| `docker-compose.yml` | базовый стенд: mock-сервисы, БД, очередь, метрики | task_78, task_114, task_259 |
| `docker-compose.test.yml` | только то, что нужно тестам: быстро поднимается и гасится | task_139–143, task_266 |
| `docker-compose.full.yml` | полный стенд: 7+ сервисов для сквозного сценария года | task_262, task_302 |
| `.env.example` | шаблон переменных окружения | task_134, task_261, task_264 |
| `nginx/` | обратный прокси: единая точка входа, TLS, лимиты | task_93, task_260 |
| `rabbitmq/` | определения очередей, обменников, политик DLQ | task_111, task_112 |
| `ci/` | конфигурация CI: сборка, тесты, релиз | task_265–270 |
| `sql/` | скрипты MS SQL по категориям (исследование, анализ, обслуживание, витрины, ETL, диагностика, бэкапы, выгрузка) | task_181–198, task_205–216 |
| `bi/` | материалы BI-трека: витрины, дашборды, семантика | task_205–210 |

## Быстрый старт

```bash
cd 1c/internship/tools
cp .env.example .env            # и заполните значения под свой стенд
docker compose up -d            # базовый стенд
docker compose ps               # все сервисы должны быть healthy
docker compose logs -f mock_shop_api
docker compose down             # остановить
docker compose down -v          # остановить и удалить данные (чистый старт)
```

Только для тестов:

```bash
docker compose -f docker-compose.test.yml up -d --wait
# ... прогон тестов ...
docker compose -f docker-compose.test.yml down -v
```

Полный стенд (задание task_302):

```bash
docker compose -f docker-compose.full.yml --env-file .env up -d --wait
curl -s http://localhost:8080/healthz
```

## Правила работы с compose

1. **Healthcheck обязателен** у каждого сервиса: `--wait` и `depends_on: condition: service_healthy`
   работают только с ним. Без healthcheck стенд «поднялся», а отвечать ещё не готов.
2. **Тома — именованные** (`volumes:` верхнего уровня), а не bind-mount в `/var/lib/...`:
   переносимость между Windows/Linux/Mac.
3. **Порты наружу — только у точки входа** (nginx). Остальные сервисы живут во
   внутренней сети: это отрабатывается в task_133 и task_136.
4. **Никаких секретов в `docker-compose.yml`** — только `${ПЕРЕМЕННАЯ}` из `.env`.
5. Версии образов фиксируются тегом, а не `latest`: воспроизводимость стенда (task_259).

## Если Docker недоступен

Каждый mock-сервис запускается и без контейнера:
`cd ../src/<сервис> && uvicorn app.main:app --port <порт>`.
RabbitMQ и PostgreSQL в этом случае можно заменить «заглушками» из `src/scripts/`,
но интеграционные тесты (task_141) тогда считаются выполненными частично —
отметьте это в отчёте честно.
