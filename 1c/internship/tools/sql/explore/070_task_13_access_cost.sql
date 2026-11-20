-- =============================================================================
-- task_13 (Q1): цена получения данных — три способа достать 10000 наименований
-- Аналог на PostgreSQL (платформы 1С в окружении нет; замеряется цена обращений
-- к СУБД — та же физика, что у «ссылка в цикле» против одного запроса):
--   A «ссылка в цикле»  : 10000 отдельных SELECT только наименования по ключу
--   B «объект в цикле»  : 10000 отдельных SELECT * (вся строка + «блокировка»)
--   C «запрос»          : один SELECT на весь набор
-- Запуск: psql -d rih -f 070_task_13_access_cost.sql
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS lab13;
DROP TABLE IF EXISTS lab13.warehouses;
CREATE TABLE lab13.warehouses (
    id          INT PRIMARY KEY,
    name        TEXT NOT NULL,
    type        TEXT NOT NULL,
    address     TEXT,
    payload     TEXT
);
INSERT INTO lab13.warehouses
SELECT g, 'Склад ' || g, 'Магазин', 'Адрес ' || g, repeat('x', 200)
FROM generate_series(1, 10000) AS g;

DO $$
DECLARE
    t0 TIMESTAMPTZ; v TEXT; n INT := 0;
BEGIN
    -- A: «ссылка в цикле» — отдельное обращение за каждой записью
    t0 := clock_timestamp();
    FOR i IN 1..10000 LOOP
        SELECT name INTO v FROM lab13.warehouses WHERE id = i;
        n := n + 1;
    END LOOP;
    RAISE NOTICE 'A ссылка-в-цикле: % мс (% обращений)', round(EXTRACT(EPOCH FROM clock_timestamp()-t0)*1000), n;

    -- B: «объект в цикле» — вся строка целиком каждую итерацию (дороже A)
    n := 0; t0 := clock_timestamp();
    FOR i IN 1..10000 LOOP
        SELECT * INTO v FROM lab13.warehouses WHERE id = i;
        n := n + 1;
    END LOOP;
    RAISE NOTICE 'B объект-в-цикле: % мс (% обращений)', round(EXTRACT(EPOCH FROM clock_timestamp()-t0)*1000), n;

    -- C: один запрос на весь набор
    t0 := clock_timestamp();
    SELECT COUNT(*) INTO n FROM (SELECT name FROM lab13.warehouses) q;
    RAISE NOTICE 'C один запрос: % мс (% строк за 1 обращение)', round(EXTRACT(EPOCH FROM clock_timestamp()-t0)*1000), n;
END $$;
