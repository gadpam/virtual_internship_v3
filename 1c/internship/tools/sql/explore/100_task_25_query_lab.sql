-- Лаборатория sprint_5 (task_25..30): аналог складских данных для запросов.
-- Источники: движения — lab22 (100 000), цены — lab23. Каталоги строятся из них.
-- Подключение: psql -h /tmp/walk-pg -U rih -d rih -f 100_task_25_query_lab.sql
CREATE SCHEMA IF NOT EXISTS labq;
DROP TABLE IF EXISTS labq.movements, labq.products, labq.groups, labq.warehouses, labq.prices, labq.min_stock CASCADE;

CREATE TABLE labq.groups (name text PRIMARY KEY, parent text);
INSERT INTO labq.groups VALUES
 ('Продукты питания', NULL), ('Молочные продукты','Продукты питания'),
 ('Бакалея','Продукты питания'), ('Напитки','Продукты питания'), ('Бытовая химия', NULL);

CREATE TABLE labq.warehouses (code text PRIMARY KEY, name text, type text);
INSERT INTO labq.warehouses SELECT DISTINCT warehouse, 'Склад '||warehouse,
       CASE WHEN warehouse='WH-1' THEN 'РЦ' ELSE 'Магазин' END FROM lab22.movements;

CREATE TABLE labq.products (sku text PRIMARY KEY, name text, grp text REFERENCES labq.groups(name));
INSERT INTO labq.products
SELECT DISTINCT product, 'Товар '||product,
       (ARRAY['Молочные продукты','Бакалея','Напитки','Бытовая химия'])[1 + (abs(hashtext(product)) % 4)]
FROM lab22.movements;

CREATE TABLE labq.movements AS SELECT * FROM lab22.movements;
CREATE INDEX ON labq.movements (warehouse, product, period);
CREATE INDEX ON labq.movements (period);

CREATE TABLE labq.prices AS SELECT * FROM lab23.prices;
-- один товар заведомо без цены (для анти-соединения task_25)
INSERT INTO labq.products VALUES ('SKU-99999','Товар без цены','Бакалея');
INSERT INTO labq.movements SELECT now(), 'doc-open', 'Приход', 'WH-1', 'SKU-99999', 3;

CREATE TABLE labq.min_stock (warehouse text, product text, minimum numeric(15,3),
                             PRIMARY KEY (warehouse, product));
INSERT INTO labq.min_stock
SELECT w.code, p.sku, 10 FROM labq.warehouses w CROSS JOIN (SELECT sku FROM labq.products LIMIT 50) p;

ANALYZE labq.movements; ANALYZE labq.products; ANALYZE labq.prices;
