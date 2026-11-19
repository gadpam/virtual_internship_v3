-- =============================================================================
-- 15 правил качества данных для прайс-листов поставщиков
-- Задание : task_212
-- Диалект : PostgreSQL
--
-- Каждое правило: код, описание, критичность, порог, проверяющий SQL.
-- Критичность block  — строка не грузится, при превышении порога партия отклоняется;
--            warn    — строка грузится с пометкой, инцидент владельцу данных;
--            info    — фиксируется в отчёте, действий не требует.
-- =============================================================================

CREATE TABLE IF NOT EXISTS staging.dq_rules (
    rule_code     TEXT PRIMARY KEY,
    rule_name     TEXT NOT NULL,
    entity        TEXT NOT NULL,
    severity      TEXT NOT NULL CHECK (severity IN ('block', 'warn', 'info')),
    threshold_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
    check_sql     TEXT NOT NULL,
    owner_role    TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS staging.dq_results (
    result_id     BIGSERIAL PRIMARY KEY,
    batch_id      TEXT NOT NULL,
    rule_code     TEXT NOT NULL REFERENCES staging.dq_rules (rule_code),
    checked_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    rows_checked  INTEGER NOT NULL DEFAULT 0,
    rows_failed   INTEGER NOT NULL DEFAULT 0,
    failed_pct    NUMERIC(6,2) NOT NULL DEFAULT 0,
    is_valid      BOOLEAN NOT NULL DEFAULT TRUE,
    action_taken  TEXT,
    sample_refs   TEXT[]
);

CREATE INDEX IF NOT EXISTS ix_dq_results_batch ON staging.dq_results (batch_id, rule_code);

INSERT INTO staging.dq_rules (rule_code, rule_name, entity, severity, threshold_pct, check_sql, owner_role) VALUES
('DQ-01', 'Артикул обязателен',                'price_list', 'block', 0.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND (sku_raw IS NULL OR btrim(sku_raw) = '''')',
 'Владелец НСИ'),
('DQ-02', 'Артикул найден в справочнике товаров','price_list', 'block', 2.00,
 'SELECT COUNT(*) FROM staging.price_list_raw r WHERE batch_id = :batch AND NOT EXISTS (SELECT 1 FROM marts.dim_product p WHERE p.sku = btrim(r.sku_raw))',
 'Владелец НСИ'),
('DQ-03', 'Цена — число',                      'price_list', 'block', 0.50,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND price_raw !~ ''^-?[0-9]+([.,][0-9]+)?$''',
 'Аналитик закупок'),
('DQ-04', 'Цена больше нуля',                  'price_list', 'block', 0.50,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND price_raw ~ ''^-?[0-9]+([.,][0-9]+)?$'' AND replace(price_raw, '','', ''.'')::numeric <= 0',
 'Аналитик закупок'),
('DQ-05', 'Цена в разумном диапазоне',         'price_list', 'warn', 5.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND replace(price_raw, '','', ''.'')::numeric > 50000',
 'Аналитик закупок'),
('DQ-06', 'Отклонение цены от предыдущей ≤ 30%','price_list','warn', 3.00,
 'WITH cur AS (SELECT btrim(sku_raw) sku, replace(price_raw,'','',''.'')::numeric price FROM staging.price_list_raw WHERE batch_id = :batch AND price_raw ~ ''^[0-9]+([.,][0-9]+)?$''), prev AS (SELECT DISTINCT ON (p.sku) p.sku, c.price FROM marts.dim_product p JOIN marts.fact_supplier_price c ON c.product_key = p.product_key ORDER BY p.sku, c.valid_from DESC) SELECT COUNT(*) FROM cur JOIN prev USING (sku) WHERE prev.price > 0 AND abs(cur.price - prev.price) / prev.price > 0.30',
 'Аналитик закупок'),
('DQ-07', 'Валюта из разрешённого списка',     'price_list', 'block', 0.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND upper(btrim(currency_raw)) NOT IN (''BYN'', ''RUB'', ''USD'', ''EUR'')',
 'Финансовый контролёр'),
('DQ-08', 'Дата начала действия корректна',    'price_list', 'block', 1.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND valid_from_raw !~ ''^[0-9]{4}-[0-9]{2}-[0-9]{2}$'' AND valid_from_raw !~ ''^[0-9]{2}\\.[0-9]{2}\\.[0-9]{4}$''',
 'Аналитик закупок'),
('DQ-09', 'Дата начала не в далёком прошлом',  'price_list', 'warn', 5.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND to_date(regexp_replace(valid_from_raw, ''(\\d{2})\\.(\\d{2})\\.(\\d{4})'', ''\\3-\\2-\\1''), ''YYYY-MM-DD'') < CURRENT_DATE - 365',
 'Аналитик закупок'),
('DQ-10', 'Нет дублей артикула в партии',      'price_list', 'block', 0.00,
 'SELECT COUNT(*) FROM (SELECT btrim(sku_raw) sku, COUNT(*) c FROM staging.price_list_raw WHERE batch_id = :batch GROUP BY 1 HAVING COUNT(*) > 1) d',
 'Владелец НСИ'),
('DQ-11', 'Наименование не пустое',            'price_list', 'warn', 5.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND (name_raw IS NULL OR btrim(name_raw) = '''')',
 'Владелец НСИ'),
('DQ-12', 'Наименование без управляющих символов','price_list','warn', 1.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND name_raw ~ E''[\\u0000-\\u0008\\u000B\\u000C\\u000E-\\u001F]''',
 'Владелец НСИ'),
('DQ-13', 'Единица измерения стандартна',      'price_list', 'info', 10.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND btrim(unit_raw) NOT IN (''шт'', ''кг'', ''л'', ''уп'')',
 'Владелец НСИ'),
('DQ-14', 'Поставщик известен',                'price_list', 'block', 0.00,
 'SELECT COUNT(*) FROM staging.price_list_raw WHERE batch_id = :batch AND NOT EXISTS (SELECT 1 FROM staging.dim_supplier s WHERE s.supplier_code = btrim(supplier_code))',
 'Аналитик закупок'),
('DQ-15', 'Размер партии в ожидаемых пределах','price_list', 'warn', 0.00,
 'SELECT CASE WHEN COUNT(*) BETWEEN 1 AND 100000 THEN 0 ELSE COUNT(*) END FROM staging.price_list_raw WHERE batch_id = :batch',
 'Инженер данных')
ON CONFLICT (rule_code) DO UPDATE
SET rule_name     = EXCLUDED.rule_name,
    entity        = EXCLUDED.entity,
    severity      = EXCLUDED.severity,
    threshold_pct = EXCLUDED.threshold_pct,
    check_sql     = EXCLUDED.check_sql,
    owner_role    = EXCLUDED.owner_role;

-- ---------------------------------------------------------------------------
-- Сводка по последней партии: что прошло, что заблокировано
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW staging.v_dq_summary AS
SELECT
    r.rule_code                                   AS "Правило",
    r.rule_name                                   AS "Название",
    r.severity                                    AS "Критичность",
    r.threshold_pct                               AS "Порог %",
    res.rows_checked                              AS "Проверено",
    res.rows_failed                               AS "Нарушено",
    res.failed_pct                                AS "Нарушено %",
    res.is_valid                                  AS "Пройдено",
    res.action_taken                              AS "Действие",
    r.owner_role                                  AS "Владелец",
    res.checked_at                                AS "Проверено в"
FROM staging.dq_rules AS r
LEFT JOIN LATERAL (
    SELECT * FROM staging.dq_results AS d
    WHERE d.rule_code = r.rule_code
    ORDER BY d.checked_at DESC
    LIMIT 1
) AS res ON TRUE
ORDER BY r.rule_code;

-- ---------------------------------------------------------------------------
-- Функция прогона правил для конкретной партии
-- Правила DQ-01..DQ-15 выполняются по списку; результат пишется в dq_results.
-- Текст check_sql подставляется с :batch — замена выполняется на стороне вызывающего
-- скрипта (psql -v batch=...) или Python-конвейера, чтобы не использовать EXECUTE
-- с динамической подстановкой пользовательских значений.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION staging.dq_register_result(
    p_batch_id   TEXT,
    p_rule_code  TEXT,
    p_rows_checked INTEGER,
    p_rows_failed  INTEGER,
    p_action     TEXT DEFAULT NULL,
    p_sample     TEXT[] DEFAULT NULL
) RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_rule       staging.dq_rules;
    v_failed_pct NUMERIC(6,2);
    v_is_valid   BOOLEAN;
    v_id         BIGINT;
BEGIN
    SELECT * INTO STRICT v_rule FROM staging.dq_rules WHERE rule_code = p_rule_code AND is_active;

    v_failed_pct := CASE WHEN p_rows_checked = 0 THEN 0
                         ELSE ROUND(100.0 * p_rows_failed / p_rows_checked, 2) END;

    v_is_valid := CASE
        WHEN v_rule.severity = 'block' AND p_rows_failed > 0                       THEN FALSE
        WHEN v_rule.severity = 'block' AND v_failed_pct > v_rule.threshold_pct     THEN FALSE
        WHEN v_rule.severity = 'warn'  AND v_failed_pct > v_rule.threshold_pct     THEN FALSE
        ELSE TRUE
    END;

    INSERT INTO staging.dq_results (batch_id, rule_code, rows_checked, rows_failed, failed_pct, is_valid, action_taken, sample_refs)
    VALUES (p_batch_id, p_rule_code, p_rows_checked, p_rows_failed, v_failed_pct, v_is_valid, p_action, p_sample)
    RETURNING result_id INTO v_id;

    RETURN v_id;
END;
$$;

COMMENT ON FUNCTION staging.dq_register_result IS
    'Регистрирует результат проверки правила и решает, прошла ли партия. Блокирующее правило с нарушениями → is_valid = FALSE (task_212).';
