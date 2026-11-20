-- =============================================================================
-- Витрина продаж по дням: marts.fact_sales_daily
-- Задание : task_122 (зерно и наполнение), ADR-0008
-- Диалект : PostgreSQL 14+ (идемпотентно)
-- Зерно   : одна строка = день × магазин × товар. Мельче — строка чека
--           (fact_sales, task_205), крупнее — нельзя ответить «что продал
--           магазин по товару за день», главный вопрос витрины.
-- Источник: выгрузка регистра «Продажи» 1С (staging.sales_turnover).
-- Наполнение: полная перезапись периода (DELETE периода -> INSERT),
--           один способ идемпотентности, как в РИХ_Витрины.
-- Измерения: dim_date/dim_store/dim_product из 010_schema.sql, SCD-1:
--           переименование товара меняет имя и в истории витрины
--           (осознанно; история атрибутов — SCD-2, Q3/BI).
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.fact_sales_daily (
    date_key     DATE    NOT NULL REFERENCES marts.dim_date (date_key),
    store_key    INTEGER NOT NULL REFERENCES marts.dim_store (store_key),
    product_key  BIGINT  NOT NULL REFERENCES marts.dim_product (product_key),
    quantity     NUMERIC(18,3) NOT NULL DEFAULT 0,  -- нетто: продажи минус возвраты
    amount       NUMERIC(18,2) NOT NULL DEFAULT 0,  -- выручка нетто возвратов
    cost         NUMERIC(18,2) NOT NULL DEFAULT 0,  -- себестоимость источника
    margin       NUMERIC(18,2) NOT NULL DEFAULT 0,  -- amount - cost, считается при загрузке
    loaded_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (date_key, store_key, product_key)
);

COMMENT ON TABLE marts.fact_sales_daily IS
    'Витрина продаж зерном день*магазин*товар (task_122). Пустых продаж нет: отсутствие строки = не было продаж; нулевая строка = продажи и возвраты сравнялись.';

CREATE INDEX IF NOT EXISTS ix_fact_sales_daily_product
    ON marts.fact_sales_daily (product_key, date_key);
