-- task_58: индексы на аналоге регистра ТоварыНаСкладах (lab55.movements, 1 млн).
-- Источник: витрины стенда (живой ИБ нет) — методика та же, что для таблиц 1С:
-- смотрим существующие индексы, снимаем план, меняем индекс, меряем снова.
-- Подключение: psql -h /tmp/walk-pg -U rih -d rih -f 140_task_58_indexes.sql

-- 1) Что есть сейчас
SELECT indexname, indexdef FROM pg_indexes WHERE schemaname = 'lab55';

-- 2) Медленный случай: пара без составного индекса под рукой СУБД
DROP INDEX IF EXISTS lab55.movements_warehouse_product_idx;
EXPLAIN (ANALYZE, COSTS OFF)
SELECT SUM(qty) FROM lab55.movements WHERE warehouse = 'WH-3' AND product = 'SKU-777';

-- 3) Индексируемый реквизит (в метаданных — составной индекс регистра)
CREATE INDEX ON lab55.movements (warehouse, product);
ANALYZE lab55.movements;
EXPLAIN (ANALYZE, COSTS OFF)
SELECT SUM(qty) FROM lab55.movements WHERE warehouse = 'WH-3' AND product = 'SKU-777';

-- 4) Цена индекса: вставка пачки с индексом и без (размер таблицы/индекса)
SELECT pg_size_pretty(pg_total_relation_size('lab55.movements')) AS таблица_с_индексами,
       pg_size_pretty(pg_relation_size('lab55.movements')) AS только_таблица;
