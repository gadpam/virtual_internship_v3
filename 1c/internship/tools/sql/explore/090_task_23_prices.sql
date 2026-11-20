-- task_23: аналог периодического РС ЦеныНоменклатуры и двух запросов «цена на дату».
-- Вариант A — аналог СРЕЗ ПОСЛЕДНИХ (DISTINCT ON по убыванию периода).
-- Вариант B — явный подзапрос (MAX Периода по измерениям + соединение назад).
-- Подключение: psql -h /tmp/walk-pg -U rih -d rih -f 090_task_23_prices.sql
CREATE SCHEMA IF NOT EXISTS lab23;
DROP TABLE IF EXISTS lab23.prices;
CREATE TABLE lab23.prices (
    period     date NOT NULL,
    recorder   text NOT NULL,
    product    text NOT NULL,
    warehouse  text NOT NULL,
    price_type text NOT NULL,
    price      numeric(15,2) NOT NULL,
    PRIMARY KEY (period, product, warehouse, price_type)
);
CREATE INDEX ON lab23.prices (product, warehouse, price_type, period DESC);

INSERT INTO lab23.prices VALUES
 ('2026-01-01','УстановкаЦен-1','SKU-00001','WH-1','Розничная',100.00),
 ('2026-02-01','УстановкаЦен-2','SKU-00001','WH-1','Розничная',110.00),
 ('2026-03-01','УстановкаЦен-3','SKU-00001','WH-1','Розничная',105.00),
 ('2026-01-15','УстановкаЦен-1','SKU-00001','WH-2','Розничная',120.00);
-- массовая история для замера
INSERT INTO lab23.prices
SELECT DATE '2020-01-01' + (g % 2000), 'bulk-'||g, 'SKU-'||(g % 2000),
       'WH-'||(g % 5), 'Розничная', 50 + (g % 100)
FROM generate_series(1, 50000) g
ON CONFLICT DO NOTHING;
ANALYZE lab23.prices;

-- A: СрезПоследних на 2026-02-15
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT DISTINCT ON (product, warehouse, price_type) product, warehouse, price_type, price
FROM lab23.prices
WHERE period <= DATE '2026-02-15'
ORDER BY product, warehouse, price_type, period DESC;

-- B: явный подзапрос
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF)
SELECT p.product, p.warehouse, p.price_type, p.price
FROM lab23.prices p
JOIN (SELECT product, warehouse, price_type, MAX(period) AS max_period
      FROM lab23.prices WHERE period <= DATE '2026-02-15'
      GROUP BY product, warehouse, price_type) last
  ON last.product = p.product AND last.warehouse = p.warehouse
 AND last.price_type = p.price_type AND last.max_period = p.period;
