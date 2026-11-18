# Доступы, RLS и маскирование в BI (task_208, task_291)

## Роли

| Роль | Что видит | Ограничения |
|---|---|---|
| `rih_analyst_selfservice` | песочница: `marts.v_sales_masked`, `v_metrics_dictionary`, свои запросы в SQL Lab | нет `dim_counterparty`, нет прямых идентификаторов, только чтение |
| `rih_commercial` | дашборд «Продажи по дням», своя сеть магазинов | RLS по `store_key`/городу |
| `rih_duty_engineer` | дашборд «Здоровье интеграций», журнал инцидентов | без финансовых детализаций по контрагентам |
| `rih_data_owner` | дашборд «Качество данных», staging-слой | может запускать ETL-скрипты по согласованию |
| `rih_bi_admin` | всё + администрирование Superset | каждый доступ журналируется, пересмотр раз в квартал (task_290) |

## RLS: как ограничить строки

Superset RLS работает через дополнительные предикаты к dataset'у для роли.
Учебная схема:

| Роль | Клауза | Эффект |
|---|---|---|
| `rih_commercial_minsk` | `city = 'Минск'` | видит только минские магазины |
| `rih_commercial_brest` | `city IN ('Брест', 'Гродно')` | видит западный регион |
| `rih_duty_engineer` | `system_code IN ('shop','loyalty','tk','bank','tracker','ai')` | только интеграции |

Проверка RLS — обязательная часть приёмки: зайдите под тестовой ролью и
убедитесь, что чужие строки **не видны**, а не «видны, но пустые».

## Маскирование персональных данных

1. Прямые идентификаторы заменяются хешем: `md5(doc_ref)` в `marts.v_sales_masked`.
2. Номер чека, ФИО, телефон, адрес — не попадают в витрины self-service.
3. `marts.dim_counterparty.is_personal_data = TRUE` → строки доступны только
   роли с основанием (договор, согласие, служебная необходимость).
4. Любая выгрузка с ПДн пишется в `staging.export_audit` с полями `contains_pd`,
   `masked`, `legal_basis` (task_124).

## Песочница self-service

Аналитикам нужен доступ к данным без очереди задач на разработку. Границы песочницы:

- **можно:** читать представления `marts.v_*`, строить свои дашборды в личной папке,
  запускать SELECT в SQL Lab;
- **нельзя:** DDL/DML, доступ к `staging.*_raw`, чтение `pg_catalog` сверх необходимого,
  экспорт без записи в журнал;
- **лимиты:** `statement_timeout = 60s`, `work_mem` ограничен, параллельные запросы — 2.

```sql
-- Учебная настройка ограничений роли песочницы
ALTER ROLE rih_analyst_selfservice SET statement_timeout = '60s';
ALTER ROLE rih_analyst_selfservice SET work_mem = '16MB';
GRANT USAGE ON SCHEMA marts TO rih_analyst_selfservice;
GRANT SELECT ON marts.v_sales_masked, marts.v_metrics_dictionary, marts.v_freshness TO rih_analyst_selfservice;
REVOKE ALL ON SCHEMA staging FROM rih_analyst_selfservice;
```

## Пересмотр доступов

Раз в квартал (task_290): список ролей и пользователей → сверка с фактическими
задачами → отзыв лишних. Отчёт о пересмотре сохраняется в `documentation/`,
иначе через год никто не помнит, почему у подрядчика есть доступ к финансовой витрине.
