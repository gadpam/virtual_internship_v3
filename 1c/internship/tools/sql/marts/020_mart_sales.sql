-- =============================================================================
-- Витрина продаж: marts.fact_sales + согласованные представления
-- Задание : task_122 (измерения и факты), task_207 (дашборды), task_208 (доступы)
-- Диалект : PostgreSQL
-- Источник: данные, выгруженные из 1С (регистр накопления «Продажи» + документы)
-- SLA     : обновление не позднее 06:00 следующего дня (см. marts.v_freshness)
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.fact_sales (
    sale_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    date_key       DATE        NOT NULL REFERENCES marts.dim_date (date_key),
    store_key      INTEGER     NOT NULL REFERENCES marts.dim_store (store_key),
    product_key    BIGINT      NOT NULL REFERENCES marts.dim_product (product_key),
    doc_number     TEXT,
    doc_ref        TEXT,                 -- ссылка на документ 1С (строковый UUID)
    channel        TEXT        NOT NULL DEFAULT 'offline',  -- offline | online | b2b
    quantity       NUMERIC(18,3) NOT NULL DEFAULT 0,
    price          NUMERIC(18,4) NOT NULL DEFAULT 0,
    discount       NUMERIC(18,2) NOT NULL DEFAULT 0,
    revenue        NUMERIC(18,2) NOT NULL DEFAULT 0,
    cost           NUMERIC(18,2) NOT NULL DEFAULT 0,
    bonus_accrued  NUMERIC(18,2) NOT NULL DEFAULT 0,
    loaded_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    source_system  TEXT        NOT NULL DEFAULT 'RIH_1C',
    CONSTRAINT ck_fact_sales_quantity CHECK (quantity >= 0),
    CONSTRAINT ck_fact_sales_revenue  CHECK (revenue >= 0),
    UNIQUE (doc_ref, product_key)      -- защита от двойной загрузки одного документа
);

COMMENT ON TABLE marts.fact_sales IS
    'Факт продаж. Выручка считается как price*quantity - discount и НЕ пересчитывается в отчётах BI: формула зафиксирована здесь (словарь метрик M-001).';

CREATE INDEX IF NOT EXISTS ix_fact_sales_date_store ON marts.fact_sales (date_key, store_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_product    ON marts.fact_sales (product_key, date_key);
CREATE INDEX IF NOT EXISTS ix_fact_sales_channel    ON marts.fact_sales (channel, date_key);

-- ---------------------------------------------------------------------------
-- Представление для дашбордов: готовые меры, чтобы аналитик не считал их сам
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW marts.v_sales_daily AS
SELECT
    f.date_key,
    d.year,
    d.quarter,
    d.month,
    d.week_iso,
    d.is_weekend,
    s.store_code,
    s.store_name,
    s.city,
    s.format,
    f.channel,
    COUNT(*)                                        AS lines_count,
    SUM(f.quantity)                                 AS quantity,
    SUM(f.revenue)                                  AS revenue,
    SUM(f.cost)                                     AS cost,
    SUM(f.revenue) - SUM(f.cost)                    AS gross_profit,
    CASE WHEN SUM(f.revenue) = 0 THEN NULL
         ELSE ROUND(100.0 * (SUM(f.revenue) - SUM(f.cost)) / SUM(f.revenue), 2)
    END                                             AS margin_pct,
    SUM(f.discount)                                 AS discount_total,
    CASE WHEN COUNT(*) = 0 THEN NULL
         ELSE ROUND(SUM(f.revenue) / COUNT(*), 2)
    END                                             AS avg_line_revenue,
    SUM(f.bonus_accrued)                            AS bonus_accrued
FROM marts.fact_sales AS f
JOIN marts.dim_date      AS d ON d.date_key    = f.date_key
JOIN marts.dim_store     AS s ON s.store_key   = f.store_key
GROUP BY f.date_key, d.year, d.quarter, d.month, d.week_iso, d.is_weekend,
         s.store_code, s.store_name, s.city, s.format, f.channel;

COMMENT ON VIEW marts.v_sales_daily IS 'Ежедневные продажи по магазинам и каналам. Основа дашборда «Продажи» (task_207).';

-- ---------------------------------------------------------------------------
-- Учебные данные: без них дашборд пустой и проверить SLA невозможно
-- ---------------------------------------------------------------------------
INSERT INTO marts.fact_sales
    (date_key, store_key, product_key, doc_number, doc_ref, channel, quantity, price, discount, revenue, cost, bonus_accrued)
SELECT
    dd.date_key,
    st.store_key,
    pr.product_key,
    'ПР-' || to_char(dd.date_key, 'YYYYMMDD') || '-' || g.n,
    md5(random()::text || g.n::text),
    CASE WHEN g.n % 5 = 0 THEN 'online' WHEN g.n % 11 = 0 THEN 'b2b' ELSE 'offline' END,
    ROUND((1 + random() * 8)::numeric, 3),
    ROUND((2 + random() * 40)::numeric, 4),
    ROUND((random() * 3)::numeric, 2),
    ROUND(((1 + random() * 8) * (2 + random() * 40))::numeric, 2),
    ROUND(((1 + random() * 8) * (1.5 + random() * 30))::numeric, 2),
    ROUND((random() * 2)::numeric, 2)
FROM marts.dim_date AS dd
CROSS JOIN marts.dim_store AS st
CROSS JOIN marts.dim_product AS pr
CROSS JOIN generate_series(1, 3) AS g(n)
WHERE dd.date_key BETWEEN CURRENT_DATE - 90 AND CURRENT_DATE
  AND st.is_active
ON CONFLICT DO NOTHING;

ANALYZE marts.fact_sales;
