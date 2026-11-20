-- =============================================================================
-- BI-доступ к витринам (task_126): только витрины, только чтение.
-- Superset ходит под пользователем bi_reader: staging и остальные
-- схемы ему закрыты — доступов «на всякий случай» не бывает.
-- Диалект: PostgreSQL. Роль создаёт администратор стенда (DBA);
-- гранты ниже выдаёт владелец схемы.
-- =============================================================================

-- Денормализация суточной витрины task_122 для дашбордов.
CREATE OR REPLACE VIEW marts.v_mart_sales_daily AS
SELECT f.date_key AS sale_date,
       s.store_code,
       s.store_name,
       p.sku,
       p.product_name,
       f.quantity AS qty,
       f.amount,
       f.cost,
       f.margin,
       f.loaded_at
FROM marts.fact_sales_daily AS f
JOIN marts.dim_store AS s ON s.store_key = f.store_key
JOIN marts.dim_product AS p ON p.product_key = f.product_key;

GRANT USAGE ON SCHEMA marts TO bi_reader;
GRANT SELECT ON marts.v_sales_daily, marts.v_mart_sales_daily,
    marts.fact_sales, marts.fact_sales_daily,
    marts.dim_date, marts.dim_store, marts.dim_product,
    marts.metrics_dictionary, marts.v_freshness, marts.etl_runs
    TO bi_reader;
