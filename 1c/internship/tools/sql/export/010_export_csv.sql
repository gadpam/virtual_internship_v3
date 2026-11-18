-- =============================================================================
-- Выгрузка витрины в CSV
-- Задание : task_124
-- Диалект : PostgreSQL
-- Примечание: COPY ... TO выполняется на стороне СЕРВЕРА; для клиентской выгрузки
--             используйте \copy в psql (см. export/README.md).
-- =============================================================================

-- 1. Продажи за 30 дней: формат, который одинаково читают Excel, 1С и Superset
SELECT
    d.date_key                       AS "Дата",
    s.store_code                     AS "КодМагазина",
    s.store_name                     AS "Магазин",
    s.city                           AS "Город",
    f.channel                        AS "Канал",
    SUM(f.quantity)                  AS "Количество",
    SUM(f.revenue)                   AS "Выручка",
    SUM(f.cost)                      AS "Себестоимость",
    SUM(f.revenue) - SUM(f.cost)     AS "ВаловаяПрибыль",
    SUM(f.discount)                  AS "Скидки"
FROM marts.fact_sales AS f
JOIN marts.dim_date  AS d ON d.date_key  = f.date_key
JOIN marts.dim_store AS s ON s.store_key = f.store_key
WHERE f.date_key >= CURRENT_DATE - 30
GROUP BY d.date_key, s.store_code, s.store_name, s.city, f.channel
ORDER BY d.date_key, s.store_code;

-- 2. Контрольные суммы для сверки после выгрузки
SELECT
    COUNT(*)                                        AS "Строк",
    SUM(f.revenue)                                  AS "СуммаВыручки",
    md5(string_agg(f.date_key::text || f.revenue::text, ',' ORDER BY f.date_key, f.revenue)) AS "КонтрольнаяСумма"
FROM marts.fact_sales AS f
WHERE f.date_key >= CURRENT_DATE - 30;

-- 3. Серверная выгрузка файла (путь должен быть доступен процессу postgres)
-- COPY (
--     SELECT * FROM marts.v_sales_daily WHERE date_key >= CURRENT_DATE - 30
-- ) TO '/var/lib/postgresql/export/sales_30d.csv'
--   WITH (FORMAT csv, HEADER true, DELIMITER ';', ENCODING 'UTF8', NULL '');

-- 4. Регистрация факта выгрузки в журнале.
--    Требует предварительно выполненного 030_export_audit.sql (он создаёт журнал).
INSERT INTO staging.export_audit (export_code, format, target, rows_exported, checksum, purpose, requested_by)
VALUES ('EXPORT_SALES_30D', 'csv', 'Финансовый аналитик', NULL, NULL,
        'Ежемесячная сверка выручки', 'dezhurnyy@rih.local');
