-- =============================================================================
-- Контроль свежести и качества витрин (task_210, task_212)
-- Диалект : PostgreSQL
-- =============================================================================

-- 1. Свежесть витрин: нарушен ли SLA загрузки
CREATE OR REPLACE VIEW marts.v_freshness AS
WITH expected AS (
    SELECT * FROM (VALUES
        ('fact_sales',        INTERVAL '1 day',    'T+1 до 06:00'),
        ('fact_integration',  INTERVAL '15 minutes','почти реальное время'),
        ('dim_product',       INTERVAL '1 day',    'T+1'),
        ('dim_store',         INTERVAL '7 days',   'по изменению')
    ) AS t(mart_name, sla_interval, sla_text)
)
SELECT
    e.mart_name                                            AS "Витрина",
    e.sla_text                                             AS "SLA",
    r.finished_at                                          AS "Последняя загрузка",
    r.status                                               AS "Статус",
    r.rows_loaded                                          AS "Загружено строк",
    r.rows_rejected                                        AS "Отклонено строк",
    ROUND(EXTRACT(EPOCH FROM (now() - r.finished_at)) / 60.0, 1) AS "Минут назад",
    CASE
        WHEN r.finished_at IS NULL THEN 'НЕТ ДАННЫХ'
        WHEN now() - r.finished_at > e.sla_interval THEN 'НАРУШЕН SLA'
        ELSE 'в норме'
    END                                                    AS "Вывод"
FROM expected AS e
LEFT JOIN LATERAL (
    SELECT finished_at, status, rows_loaded, rows_rejected
    FROM marts.etl_runs
    WHERE mart_name = e.mart_name AND status IN ('ok', 'partial')
    ORDER BY started_at DESC
    LIMIT 1
) AS r ON TRUE
ORDER BY "Вывод" DESC, "Витрина";

-- 2. Журнал прогонов ETL за сутки: что падало и почему
CREATE OR REPLACE VIEW marts.v_etl_runs_24h AS
SELECT
    run_id,
    mart_name,
    started_at,
    finished_at,
    EXTRACT(EPOCH FROM (finished_at - started_at))::int AS duration_sec,
    rows_loaded,
    rows_rejected,
    status,
    period_from,
    period_to,
    LEFT(error_text, 500)                               AS error_excerpt
FROM marts.etl_runs
WHERE started_at >= now() - INTERVAL '24 hours'
ORDER BY started_at DESC;

-- 3. Аномалии в витрине продаж: дни с подозрительно малым или большим объёмом
CREATE OR REPLACE VIEW marts.v_sales_anomalies AS
WITH daily AS (
    SELECT date_key, SUM(revenue) AS revenue
    FROM marts.fact_sales
    GROUP BY date_key
), stats AS (
    SELECT AVG(revenue) AS avg_revenue, STDDEV(revenue) AS sd_revenue FROM daily
)
SELECT
    d.date_key                                          AS "Дата",
    ROUND(d.revenue, 2)                                 AS "Выручка",
    ROUND(s.avg_revenue, 2)                             AS "Средняя",
    ROUND((d.revenue - s.avg_revenue) / NULLIF(s.sd_revenue, 0), 2) AS "Отклонений SD",
    CASE
        WHEN d.revenue < s.avg_revenue - 2 * s.sd_revenue THEN 'аномально низкая'
        WHEN d.revenue > s.avg_revenue + 2 * s.sd_revenue THEN 'аномально высокая'
        ELSE 'в норме'
    END                                                 AS "Оценка"
FROM daily AS d CROSS JOIN stats AS s
WHERE ABS(d.revenue - s.avg_revenue) > 2 * NULLIF(s.sd_revenue, 0)
ORDER BY d.date_key DESC;

COMMENT ON VIEW marts.v_sales_anomalies IS 'Простейший контроль качества витрины: аномалии видны до того, как их увидит директор в дашборде (task_212).';

-- 4. Маскирование конфиденциальных данных для self-service песочницы (task_208)
CREATE OR REPLACE VIEW marts.v_sales_masked AS
SELECT
    f.date_key,
    f.store_key,
    f.product_key,
    f.channel,
    f.quantity,
    f.revenue,
    NULL::text                                          AS doc_number,   -- номер чека не отдаём
    md5(COALESCE(f.doc_ref, ''))                        AS doc_hash,     -- связь сохраняется, идентификатор нет
    f.loaded_at
FROM marts.fact_sales AS f;

COMMENT ON VIEW marts.v_sales_masked IS
    'Представление для аналитиков без доступа к персональным данным: прямые идентификаторы заменены хешем (task_208, task_291).';
