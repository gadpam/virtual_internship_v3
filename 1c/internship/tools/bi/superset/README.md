# Подъём Superset и подключение витрин

## Запуск

Superset входит в `tools/docker-compose.full.yml`:

```bash
cd 1c/internship/tools
docker compose -f docker-compose.full.yml up -d postgres superset
docker compose logs -f superset      # первый старт: migration + superset init, 1–3 минуты
```

Вход: `http://localhost:8088`, пользователь `admin`, пароль — `SUPERSET_SECRET_KEY`
из `.env`. **Это учебное допущение**: в реальном стенде пароль администратора и
секретный ключ приложения — разные значения, и ни одно из них не хранится в Git.

## Подключение источника данных

1. Settings → Database Connections → + Database → PostgreSQL.
2. SQLAlchemy URI:
   `postgresql+psycopg2://rih:${POSTGRES_PASSWORD}@postgres:5432/rih`
   (имя хоста — сервис compose, не `localhost`: контейнер не видит ваш ноутбук).
3. Включить «Expose database in SQL Lab» — для песочницы аналитиков.
4. Datasets: добавить `marts.v_sales_daily`, `marts.v_sli_integration`,
   `staging.v_dq_summary`, `marts.v_freshness`, `marts.v_metrics_dictionary`.

## Что создавать как Dataset, а что как SQL

| Объект | Как |
|---|---|
| `marts.v_sales_daily` | Dataset (основной, для всех панелей продаж) |
| `marts.v_sli_integration` | Dataset (SLO, латентность) |
| `staging.v_dq_summary` | Dataset (качество данных) |
| `marts.v_freshness` | Dataset (баннер свежести на каждом дашборде) |
| разовые исследования | SQL в SQL Lab, результат — не дашборд |

Правило: если формулу пришлось написать в панели дашборда — её место в витрине
или в словаре метрик. Иначе через месяц три дашборда будут показывать три
«выручки».

## Экспорт и версионирование дашбордов

Superset умеет экспорт дашборда в YAML/ZIP. Экспортированные файлы кладите в
`1c/internship/build/bi/` (не в Git) и описывайте состав дашборда в
`../dashboards/*.md` — текстовая спецификация переживает смену инструмента,
а YAML-экспорт привязан к версии Superset.
