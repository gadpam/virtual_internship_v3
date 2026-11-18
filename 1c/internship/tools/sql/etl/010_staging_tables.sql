-- =============================================================================
-- Приёмный слой staging: сырые прайс-листы и служебные таблицы
-- Задание : task_211
-- Диалект : PostgreSQL (идемпотентно)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS staging;

-- 1. Сырая загрузка прайс-листа поставщика: ровно то, что прислали, без исправлений
CREATE TABLE IF NOT EXISTS staging.price_list_raw (
    raw_id        BIGSERIAL PRIMARY KEY,
    batch_id      TEXT        NOT NULL,
    supplier_code TEXT,
    file_name     TEXT,
    received_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    row_no        INTEGER     NOT NULL,
    sku_raw       TEXT,
    name_raw      TEXT,
    price_raw     TEXT,
    currency_raw  TEXT,
    unit_raw      TEXT,
    valid_from_raw TEXT,
    payload       JSONB       NOT NULL DEFAULT '{}'::jsonb,
    CONSTRAINT uq_price_list_raw UNIQUE (batch_id, row_no)
);

CREATE INDEX IF NOT EXISTS ix_price_list_raw_batch ON staging.price_list_raw (batch_id);
CREATE INDEX IF NOT EXISTS ix_price_list_raw_sku   ON staging.price_list_raw (sku_raw);

COMMENT ON TABLE staging.price_list_raw IS
    'Сырой слой. Значения хранятся как TEXT намеренно: типизация происходит после проверок качества, иначе ошибка формата убивает всю загрузку.';

-- 2. Нормализованные строки, готовые к загрузке в витрину
CREATE TABLE IF NOT EXISTS staging.price_list_clean (
    clean_id      BIGSERIAL PRIMARY KEY,
    batch_id      TEXT        NOT NULL,
    supplier_key  INTEGER,
    sku           TEXT        NOT NULL,
    product_name  TEXT,
    price         NUMERIC(18,4),
    currency      TEXT        NOT NULL DEFAULT 'BYN',
    unit          TEXT,
    valid_from    DATE,
    is_valid      BOOLEAN     NOT NULL DEFAULT TRUE,
    rejected_by_rules TEXT[],
    normalized_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_price_list_clean UNIQUE (batch_id, sku, valid_from)
);

CREATE INDEX IF NOT EXISTS ix_price_list_clean_sku ON staging.price_list_clean (sku, valid_from DESC);

-- 3. Справочник прайс-листов в витрине (факт)
CREATE TABLE IF NOT EXISTS marts.fact_supplier_price (
    price_id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    supplier_key  INTEGER     NOT NULL,
    product_key   BIGINT      NOT NULL REFERENCES marts.dim_product (product_key),
    price         NUMERIC(18,4) NOT NULL CHECK (price >= 0),
    currency      TEXT        NOT NULL DEFAULT 'BYN',
    valid_from    DATE        NOT NULL,
    valid_to      DATE,
    batch_id      TEXT        NOT NULL,
    loaded_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT uq_fact_supplier_price UNIQUE (supplier_key, product_key, valid_from)
);

CREATE INDEX IF NOT EXISTS ix_fact_supplier_price_product ON marts.fact_supplier_price (product_key, valid_from DESC);

-- 4. Справочник поставщиков staging-слоя
CREATE TABLE IF NOT EXISTS staging.dim_supplier (
    supplier_key  INTEGER PRIMARY KEY,
    supplier_code TEXT    NOT NULL UNIQUE,
    supplier_name TEXT    NOT NULL,
    unp           TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO staging.dim_supplier (supplier_key, supplier_code, supplier_name, unp)
VALUES
    (101, 'SUP-001', 'УП «Молочный край»',   '100000001'),
    (102, 'SUP-002', 'ОАО «Хлебный двор»',   '100000002'),
    (103, 'SUP-003', 'ИП Ковалёв В.В.',      '200000003'),
    (104, 'SUP-004', 'ООО «Чистый дом опт»', '100000004')
ON CONFLICT (supplier_key) DO NOTHING;

-- 5. Статусы обменов — источник метрики M-007 «Отставание обмена»
CREATE TABLE IF NOT EXISTS staging.exchange_status (
    plan_code        TEXT PRIMARY KEY,
    direction        TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
    last_success_at  TIMESTAMPTZ,
    last_error_at    TIMESTAMPTZ,
    last_error_text  TEXT,
    rows_last_run    INTEGER,
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO staging.exchange_status (plan_code, direction, last_success_at, rows_last_run)
VALUES
    ('Магазин_Заказы',    'inbound',  now() - INTERVAL '6 minutes',  128),
    ('Магазин_Остатки',   'outbound', now() - INTERVAL '12 minutes', 4210),
    ('БП_Проводки',       'outbound', now() - INTERVAL '40 minutes', 356),
    ('Лояльность_Баллы',  'outbound', now() - INTERVAL '3 minutes',  89),
    ('ДО_Документы',      'inbound',  now() - INTERVAL '3 hours',    12)
ON CONFLICT (plan_code) DO UPDATE
SET last_success_at = EXCLUDED.last_success_at,
    rows_last_run   = EXCLUDED.rows_last_run,
    updated_at      = now();

-- 6. Инциденты: источник метрики M-008
CREATE TABLE IF NOT EXISTS staging.incidents (
    incident_id   TEXT PRIMARY KEY,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    system_code   TEXT        NOT NULL,
    severity      TEXT        NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'critical')),
    status        TEXT        NOT NULL DEFAULT 'new',
    source        TEXT        NOT NULL DEFAULT 'auto',   -- auto | manual
    summary       TEXT        NOT NULL,
    correlation_id TEXT,
    resolved_at   TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS ix_incidents_created ON staging.incidents (created_at DESC);
