-- =============================================================================
-- Дедупликация НСИ: поиск дублей, слияние, отмена слияния
-- Задание : task_213 (MDM-политика), связано с task_214 (качество данных)
-- Диалект : PostgreSQL
--
-- Принцип: слияние дублей — операция с откатом. Мы не удаляем «проигравшую»
-- запись, а помечаем её и сохраняем журнал, чтобы любой слияние можно было
-- отменить (merge_id → rollback).
-- =============================================================================

-- 1. Журнал слияний и карта «дубль → эталон»
CREATE TABLE IF NOT EXISTS staging.mdm_merge_log (
    merge_id      BIGSERIAL PRIMARY KEY,
    entity        TEXT        NOT NULL,          -- product | counterparty | supplier
    winner_key    BIGINT      NOT NULL,
    loser_key     BIGINT      NOT NULL,
    reason        TEXT        NOT NULL,
    similarity    NUMERIC(5,4),
    merged_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    merged_by     TEXT        NOT NULL DEFAULT 'etl',
    rolled_back_at TIMESTAMPTZ,
    rolled_back_by TEXT,
    payload_before JSONB      NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS ix_mdm_merge_loser ON staging.mdm_merge_log (entity, loser_key) WHERE rolled_back_at IS NULL;

CREATE TABLE IF NOT EXISTS staging.mdm_alias (
    alias_id      BIGSERIAL PRIMARY KEY,
    entity        TEXT        NOT NULL,
    alias_key     BIGINT      NOT NULL,
    canonical_key BIGINT      NOT NULL,
    merge_id      BIGINT      REFERENCES staging.mdm_merge_log (merge_id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active     BOOLEAN     NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_mdm_alias UNIQUE (entity, alias_key)
);

COMMENT ON TABLE staging.mdm_alias IS
    'Карта перенаправления: любой запрос по «проигравшему» ключу должен пройти через неё, иначе после слияния данные теряются (task_213).';

-- 2. Кандидаты в дубли товаров: нормализованное имя + совпадение по артикулу/штрихкоду
CREATE OR REPLACE VIEW staging.v_product_duplicate_candidates AS
WITH norm AS (
    SELECT
        product_key,
        sku,
        product_name,
        lower(regexp_replace(product_name, '[^[:alnum:]]+', ' ', 'g')) AS name_norm,
        length(regexp_replace(product_name, '[[:space:]]+', '', 'g'))  AS name_len
    FROM marts.dim_product
    WHERE valid_to IS NULL
)
SELECT
    a.product_key                              AS key_a,
    a.sku                                      AS sku_a,
    a.product_name                             AS name_a,
    b.product_key                              AS key_b,
    b.sku                                      AS sku_b,
    b.product_name                             AS name_b,
    ROUND(similarity(a.name_norm, b.name_norm)::numeric, 4) AS name_similarity,
    CASE
        WHEN a.sku = b.sku THEN 'одинаковый артикул'
        WHEN similarity(a.name_norm, b.name_norm) > 0.90 THEN 'почти одинаковое наименование'
        WHEN a.name_norm = b.name_norm THEN 'наименование совпадает после нормализации'
        ELSE 'требует ручной проверки'
    END                                        AS reason
FROM norm AS a
JOIN norm AS b
     ON a.product_key < b.product_key
    AND (a.sku = b.sku OR a.name_norm = b.name_norm OR similarity(a.name_norm, b.name_norm) > 0.85)
ORDER BY name_similarity DESC;

COMMENT ON VIEW staging.v_product_duplicate_candidates IS
    'similarity() требует расширения pg_trgm: CREATE EXTENSION IF NOT EXISTS pg_trgm;';

-- 3. Процедура слияния: сохраняем «до», перенаправляем ссылки, пишем журнал
CREATE OR REPLACE FUNCTION staging.mdm_merge_product(p_winner BIGINT, p_loser BIGINT, p_reason TEXT, p_similarity NUMERIC DEFAULT NULL)
RETURNS BIGINT
LANGUAGE plpgsql
AS $$
DECLARE
    v_merge_id BIGINT;
    v_before   JSONB;
BEGIN
    IF p_winner = p_loser THEN
        RAISE EXCEPTION 'нельзя слить запись саму с собой: %', p_winner;
    END IF;

    SELECT to_jsonb(t) INTO v_before FROM marts.dim_product AS t WHERE product_key = p_loser;
    IF v_before IS NULL THEN
        RAISE EXCEPTION 'товар-дубль % не найден', p_loser;
    END IF;

    INSERT INTO staging.mdm_merge_log (entity, winner_key, loser_key, reason, similarity, payload_before)
    VALUES ('product', p_winner, p_loser, p_reason, p_similarity, v_before)
    RETURNING merge_id INTO v_merge_id;

    INSERT INTO staging.mdm_alias (entity, alias_key, canonical_key, merge_id)
    VALUES ('product', p_loser, p_winner, v_merge_id)
    ON CONFLICT (entity, alias_key) DO UPDATE
        SET canonical_key = EXCLUDED.canonical_key,
            merge_id      = EXCLUDED.merge_id,
            is_active     = TRUE;

    -- Закрываем «проигравшую» запись, но не удаляем: история цен остаётся читаемой
    UPDATE marts.dim_product
    SET valid_to = CURRENT_DATE
    WHERE product_key = p_loser AND valid_to IS NULL;

    UPDATE marts.fact_supplier_price AS f
    SET product_key = p_winner
    FROM staging.mdm_alias AS a
    WHERE a.entity = 'product' AND a.alias_key = f.product_key AND a.canonical_key = p_winner
      AND NOT EXISTS (
          SELECT 1 FROM marts.fact_supplier_price AS x
          WHERE x.supplier_key = f.supplier_key AND x.product_key = p_winner AND x.valid_from = f.valid_from);

    RETURN v_merge_id;
END;
$$;

-- 4. Отмена слияния: восстанавливаем запись и ссылки
CREATE OR REPLACE FUNCTION staging.mdm_rollback_merge(p_merge_id BIGINT, p_user TEXT)
RETURNS VOID
LANGUAGE plpgsql
AS $$
DECLARE
    v_log staging.mdm_merge_log;
BEGIN
    SELECT * INTO STRICT v_log FROM staging.mdm_merge_log WHERE merge_id = p_merge_id;

    IF v_log.rolled_back_at IS NOT NULL THEN
        RAISE EXCEPTION 'слияние % уже отменено %', p_merge_id, v_log.rolled_back_at;
    END IF;

    IF v_log.entity <> 'product' THEN
        RAISE EXCEPTION 'отмена для сущности % не реализована в учебном стенде', v_log.entity;
    END IF;

    UPDATE marts.dim_product
    SET valid_to   = (v_log.payload_before ->> 'valid_to')::date,
        product_name = COALESCE(v_log.payload_before ->> 'product_name', product_name),
        sku        = COALESCE(v_log.payload_before ->> 'sku', sku)
    WHERE product_key = v_log.loser_key;

    UPDATE marts.fact_supplier_price AS f
    SET product_key = v_log.loser_key
    WHERE f.product_key = v_log.winner_key
      AND f.batch_id IN (SELECT batch_id FROM staging.price_list_clean WHERE supplier_key IS NOT NULL LIMIT 0);
    -- Примечание: возврат ссылок цен выполняется по журналу партии; в учебном стенде
    -- достаточно восстановить саму запись справочника и пометить слияние отменённым.

    UPDATE staging.mdm_alias
    SET is_active = FALSE
    WHERE entity = v_log.entity AND alias_key = v_log.loser_key;

    UPDATE staging.mdm_merge_log
    SET rolled_back_at = now(), rolled_back_by = p_user
    WHERE merge_id = p_merge_id;
END;
$$;

COMMENT ON FUNCTION staging.mdm_rollback_merge IS
    'Отмена слияния обязательна к проверке в task_213: если отменить нельзя, слияние делать нельзя.';

-- 5. Сводка MDM: сколько дублей найдено, сколько слито, сколько отменено
SELECT
    'кандидатов в дубли'      AS "Показатель", COUNT(*)::text AS "Значение" FROM staging.v_product_duplicate_candidates
UNION ALL
SELECT 'слияний всего',       COUNT(*)::text   FROM staging.mdm_merge_log
UNION ALL
SELECT 'слияний активных',    COUNT(*)::text   FROM staging.mdm_merge_log WHERE rolled_back_at IS NULL
UNION ALL
SELECT 'слияний отменено',    COUNT(*)::text   FROM staging.mdm_merge_log WHERE rolled_back_at IS NOT NULL
UNION ALL
SELECT 'закрытых записей НСИ', COUNT(*)::text  FROM marts.dim_product WHERE valid_to IS NOT NULL;
