-- task_55: миллион движений — наивная и оптимизированная загрузка (аналог).
-- Профиль: 10 складов, 5 000 товаров, 100 000 документов x 10 строк = 1 000 000.
-- Склады и товары независимы (разные генераторы), период — год.
-- Подключение: psql -h /tmp/walk-pg -U rih -d rih -f 130_task_55_million.sql
CREATE SCHEMA IF NOT EXISTS lab55;
DROP TABLE IF EXISTS lab55.movements;
CREATE TABLE lab55.movements (
    period date NOT NULL, recorder text NOT NULL,
    warehouse text NOT NULL, product text NOT NULL, qty numeric(15,3) NOT NULL
);

-- ОПТИМИЗИРОВАННАЯ: один набор на миллион (аналог пакетной записи наборами)
\timing on
INSERT INTO lab55.movements
SELECT DATE '2026-01-01' + (g % 365), 'doc-' || (g / 10),
       'WH-' || (abs(hashtext('w' || g)) % 10),
       'SKU-' || (abs(hashtext('p' || g)) % 5000),
       (g % 9) + 1
FROM generate_series(1, 1000000) g;
\timing off
SELECT 'движений загружено: '||COUNT(*) FROM lab55.movements;
CREATE INDEX ON lab55.movements (warehouse, product);
ANALYZE lab55.movements;
-- отчёт после загрузки работает (остатки по складам)
EXPLAIN (ANALYZE, COSTS OFF)
SELECT warehouse, SUM(qty) FROM lab55.movements GROUP BY warehouse;
