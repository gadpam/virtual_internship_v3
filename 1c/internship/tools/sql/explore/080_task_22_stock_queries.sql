-- task_22: аналог регистра ТоварыНаСкладах в PostgreSQL (платформы 1С нет).
-- 4 запроса задания в 1С-нотации приведены в documentation/task_22_description.txt;
-- здесь меряем запрос остатков на 10 тыс. и 100 тыс. движений.
-- Подключение: psql -h /tmp/walk-pg -U rih -d rih -f 080_task_22_stock_queries.sql
CREATE SCHEMA IF NOT EXISTS lab22;
DROP TABLE IF EXISTS lab22.movements;
CREATE TABLE lab22.movements (
    period     timestamptz NOT NULL,
    recorder   text NOT NULL,
    kind       text NOT NULL CHECK (kind IN ('Приход','Расход')),
    warehouse  text NOT NULL,
    product    text NOT NULL,
    qty        numeric(15,3) NOT NULL
);
CREATE INDEX ON lab22.movements (warehouse, product, period);

-- 100 000 движений пачками документов (как проведение пачки в задании)
INSERT INTO lab22.movements
SELECT '2026-01-01'::timestamptz + (g % 300) * interval '1 day',
       'doc-' || (g / 10),
       CASE WHEN g % 7 = 0 THEN 'Расход' ELSE 'Приход' END,
       'WH-' || (g % 5),
       'SKU-' || (g % 500),
       (g % 9) + 1
FROM generate_series(1, 100000) g;

ANALYZE lab22.movements;

-- Запрос остатков (аналог виртуальной таблицы Остатки): на полном объёме
EXPLAIN (ANALYZE, BUFFERS)
SELECT warehouse, product, SUM(CASE WHEN kind='Приход' THEN qty ELSE -qty END) AS balance
FROM lab22.movements
GROUP BY warehouse, product;

-- Тот же запрос на 10 000 движений: отдельная таблица того же зерна.
-- Первая попытка среза подзапросом по регистраторам честно отброшена:
-- подзапрос всё равно сканировал все 100 000 строк (39.9 мс).
DROP TABLE IF EXISTS lab22.movements_10k;
CREATE TABLE lab22.movements_10k AS SELECT * FROM lab22.movements LIMIT 10000;
CREATE INDEX ON lab22.movements_10k (warehouse, product, period);
ANALYZE lab22.movements_10k;
EXPLAIN (ANALYZE, BUFFERS)
SELECT warehouse, product, SUM(CASE WHEN kind='Приход' THEN qty ELSE -qty END) AS balance
FROM lab22.movements_10k
GROUP BY warehouse, product;
-- Итог замера (2026-11-17): 10 тыс. -> 7.5 мс, 100 тыс. -> 40.8 мс.
-- ВАЖНО: это аналог без таблицы итогов. В 1С регистр вида «Остатки»
-- хранит готовые итоги, и виртуальная таблица Остатки не пересчитывает
-- движения: время почти не зависит от числа движений. Аналог показывает
-- цену именно пересчёта, от которой регистр нас и спасает.
