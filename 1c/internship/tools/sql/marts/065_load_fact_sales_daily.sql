-- =============================================================================
-- Загрузка суточной витрины из факта продаж (task_126, регламент task_122).
-- Полная перезапись агрегата день*магазин*товар из marts.fact_sales;
-- прогон пишется в marts.etl_runs. Запуск: 02:00, после загрузки фактов.
-- Диалект: PostgreSQL
-- =============================================================================

INSERT INTO marts.etl_runs (mart_name, started_at, finished_at, status, rows_loaded)
SELECT 'fact_sales_daily', now(), now(), 'ok', 0;

DELETE FROM marts.fact_sales_daily;

INSERT INTO marts.fact_sales_daily (date_key, store_key, product_key, quantity, amount, cost, margin)
SELECT date_key, store_key, product_key,
       sum(quantity), sum(revenue), sum(cost), sum(revenue) - sum(cost)
FROM marts.fact_sales
GROUP BY 1, 2, 3;

UPDATE marts.etl_runs
SET rows_loaded = (SELECT count(*) FROM marts.fact_sales_daily)
WHERE run_id = (SELECT max(run_id) FROM marts.etl_runs WHERE mart_name = 'fact_sales_daily');
