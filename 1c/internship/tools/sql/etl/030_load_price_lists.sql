-- =============================================================================
-- Загрузка прайс-листа: нормализация, проверки, идемпотентная вставка
-- Задание : task_211, task_212
-- Диалект : PostgreSQL
--
-- Порядок: raw → clean (с флагами валидности) → marts.fact_supplier_price.
-- Повторный прогон той же партии не создаёт дублей (batch_id в уникальном ключе).
-- =============================================================================

-- 1. Нормализация сырых строк в staging.price_list_clean
WITH normalized AS (
    SELECT
        r.batch_id,
        s.supplier_key,
        btrim(r.sku_raw)                                   AS sku,
        NULLIF(btrim(r.name_raw), '')                      AS product_name,
        CASE
            WHEN r.price_raw ~ '^-?[0-9]+([.,][0-9]+)?$'
            THEN replace(r.price_raw, ',', '.')::numeric
        END                                                AS price,
        COALESCE(NULLIF(upper(btrim(r.currency_raw)), ''), 'BYN') AS currency,
        NULLIF(btrim(r.unit_raw), '')                      AS unit,
        CASE
            WHEN r.valid_from_raw ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'
                THEN r.valid_from_raw::date
            WHEN r.valid_from_raw ~ '^[0-9]{2}\.[0-9]{2}\.[0-9]{4}$'
                THEN to_date(r.valid_from_raw, 'DD.MM.YYYY')
        END                                                AS valid_from,
        r.row_no
    FROM staging.price_list_raw AS r
    LEFT JOIN staging.dim_supplier AS s ON s.supplier_code = btrim(r.supplier_code)
),
flagged AS (
    SELECT
        n.*,
        p.product_key,
        -- Собираем список нарушенных правил прямо в строке: видно, что и почему
        ARRAY_REMOVE(ARRAY[
            CASE WHEN n.sku IS NULL OR n.sku = ''                THEN 'DQ-01' END,
            CASE WHEN p.product_key IS NULL                      THEN 'DQ-02' END,
            CASE WHEN n.price IS NULL                            THEN 'DQ-03' END,
            CASE WHEN n.price IS NOT NULL AND n.price <= 0       THEN 'DQ-04' END,
            CASE WHEN n.price > 50000                            THEN 'DQ-05' END,
            CASE WHEN n.currency NOT IN ('BYN','RUB','USD','EUR') THEN 'DQ-07' END,
            CASE WHEN n.valid_from IS NULL                       THEN 'DQ-08' END,
            CASE WHEN n.valid_from < CURRENT_DATE - 365          THEN 'DQ-09' END,
            CASE WHEN n.product_name IS NULL                     THEN 'DQ-11' END,
            CASE WHEN n.supplier_key IS NULL                     THEN 'DQ-14' END
        ], NULL)                                             AS rejected_by_rules
    FROM normalized AS n
    LEFT JOIN marts.dim_product AS p ON p.sku = n.sku
)
INSERT INTO staging.price_list_clean
    (batch_id, supplier_key, sku, product_name, price, currency, unit, valid_from, is_valid, rejected_by_rules)
SELECT
    f.batch_id, f.supplier_key, COALESCE(f.sku, ''), f.product_name, f.price, f.currency,
    f.unit, COALESCE(f.valid_from, CURRENT_DATE),
    -- блокирующие правила: DQ-01, DQ-02, DQ-03, DQ-04, DQ-07, DQ-08, DQ-14
    NOT (f.rejected_by_rules && ARRAY['DQ-01','DQ-02','DQ-03','DQ-04','DQ-07','DQ-08','DQ-14']),
    f.rejected_by_rules
FROM flagged AS f
ON CONFLICT (batch_id, sku, valid_from) DO UPDATE
SET supplier_key      = EXCLUDED.supplier_key,
    product_name      = EXCLUDED.product_name,
    price             = EXCLUDED.price,
    currency          = EXCLUDED.currency,
    unit              = EXCLUDED.unit,
    is_valid          = EXCLUDED.is_valid,
    rejected_by_rules = EXCLUDED.rejected_by_rules,
    normalized_at     = now();

-- 2. Загрузка в витрину: только валидные строки, только из непроверенных партий
INSERT INTO marts.fact_supplier_price (supplier_key, product_key, price, currency, valid_from, valid_to, batch_id)
SELECT
    c.supplier_key,
    p.product_key,
    c.price,
    c.currency,
    c.valid_from,
    LEAD(c.valid_from) OVER (PARTITION BY c.supplier_key, p.product_key ORDER BY c.valid_from) - 1,
    c.batch_id
FROM staging.price_list_clean AS c
JOIN marts.dim_product AS p ON p.sku = c.sku
WHERE c.is_valid
  AND NOT EXISTS (
      SELECT 1 FROM marts.etl_runs AS r
      WHERE r.mart_name = 'fact_supplier_price'
        AND r.status = 'ok'
        AND r.period_from = c.valid_from
        AND r.rows_loaded IS NOT NULL
  )
ON CONFLICT (supplier_key, product_key, valid_from) DO UPDATE
SET price      = EXCLUDED.price,
    currency   = EXCLUDED.currency,
    valid_to   = EXCLUDED.valid_to,
    batch_id   = EXCLUDED.batch_id,
    loaded_at  = now();

-- 3. Отчёт по загрузке: что пришло, что ушло в брак, по каким правилам
SELECT
    c.batch_id                                            AS "Партия",
    COUNT(*)                                              AS "Строк всего",
    SUM(CASE WHEN c.is_valid THEN 1 ELSE 0 END)           AS "Годных",
    SUM(CASE WHEN NOT c.is_valid THEN 1 ELSE 0 END)       AS "Брак",
    ROUND(100.0 * SUM(CASE WHEN NOT c.is_valid THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2) AS "Брак %",
    (SELECT COUNT(*) FROM marts.fact_supplier_price AS f WHERE f.batch_id = c.batch_id)     AS "Загружено в витрину"
FROM staging.price_list_clean AS c
GROUP BY c.batch_id
ORDER BY c.batch_id DESC
LIMIT 20;

-- 4. Топ причин брака: по ним пишем письмо поставщику, а не «данные плохие»
SELECT
    rule                                                  AS "Правило",
    r.rule_name                                           AS "Название",
    r.severity                                            AS "Критичность",
    r.owner_role                                          AS "Кому адресовать",
    COUNT(*)                                              AS "Строк"
FROM staging.price_list_clean AS c
CROSS JOIN LATERAL unnest(c.rejected_by_rules) AS rule
JOIN staging.dq_rules AS r ON r.rule_code = rule
WHERE NOT c.is_valid OR cardinality(c.rejected_by_rules) > 0
GROUP BY rule, r.rule_name, r.severity, r.owner_role
ORDER BY COUNT(*) DESC;

ANALYZE marts.fact_supplier_price;
ANALYZE staging.price_list_clean;
