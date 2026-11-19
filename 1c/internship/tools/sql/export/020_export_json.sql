-- =============================================================================
-- Выгрузка в JSON: формат для HTTP-сервисов и очередей
-- Задание : task_124, формат согласуется с task_74 (HTTP-сервисы 1С)
-- Диалект : PostgreSQL
-- =============================================================================

-- 1. Одна строка = один документ JSON (NDJSON-подобно): удобно для потоковой передачи
SELECT json_build_object(
    'date',        d.date_key,
    'storeCode',   s.store_code,
    'storeName',   s.store_name,
    'channel',     f.channel,
    'quantity',    SUM(f.quantity),
    'revenue',     SUM(f.revenue),
    'grossProfit', SUM(f.revenue) - SUM(f.cost),
    'currency',    'BYN'
)::text AS json_line
FROM marts.fact_sales AS f
JOIN marts.dim_date  AS d ON d.date_key  = f.date_key
JOIN marts.dim_store AS s ON s.store_key = f.store_key
WHERE f.date_key = CURRENT_DATE - 1
GROUP BY d.date_key, s.store_code, s.store_name, f.channel
ORDER BY s.store_code;

-- 2. Пакет целиком: один JSON-документ с метаданными (версия формата, счётчики)
SELECT json_build_object(
    'formatVersion', '1.0',
    'generatedAt',   to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'sourceSystem',  'RIH_marts',
    'periodFrom',    CURRENT_DATE - 30,
    'periodTo',      CURRENT_DATE,
    'rowCount',      COUNT(*),
    'items',         json_agg(row_to_json(t))
) AS payload
FROM (
    SELECT
        f.date_key       AS "date",
        s.store_code     AS "storeCode",
        f.channel        AS "channel",
        SUM(f.quantity)  AS "quantity",
        SUM(f.revenue)   AS "revenue"
    FROM marts.fact_sales AS f
    JOIN marts.dim_store AS s ON s.store_key = f.store_key
    WHERE f.date_key >= CURRENT_DATE - 30
    GROUP BY f.date_key, s.store_code, f.channel
) AS t;

-- 3. События для очереди: формат совпадает с сообщениями rih.events (task_111)
SELECT json_build_object(
    'messageId',     md5(f.date_key::text || s.store_code || f.channel),
    'eventType',     'sales.daily.aggregated',
    'occurredAt',    to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS"Z"'),
    'correlationId', 'export-' || to_char(now(), 'YYYYMMDDHH24MISS'),
    'payload',       json_build_object(
        'date',      f.date_key,
        'storeCode', s.store_code,
        'channel',   f.channel,
        'revenue',   SUM(f.revenue))
)::text AS message
FROM marts.fact_sales AS f
JOIN marts.dim_store AS s ON s.store_key = f.store_key
WHERE f.date_key = CURRENT_DATE - 1
GROUP BY f.date_key, s.store_code, f.channel
LIMIT 100;
