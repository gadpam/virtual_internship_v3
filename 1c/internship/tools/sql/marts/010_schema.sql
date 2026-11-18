-- =============================================================================
-- Слой витрин RIH: схема и измерения
-- Задание : task_205, task_122
-- Диалект : PostgreSQL 14+ (идемпотентно: выполняется при каждом старте стенда)
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS marts;
CREATE SCHEMA IF NOT EXISTS staging;

COMMENT ON SCHEMA marts   IS 'Витрины данных для BI: согласованные метрики, SLA свежести, владелец — команда RIH';
COMMENT ON SCHEMA staging IS 'Сырой слой: данные, принятые из 1С и внешних источников до проверок качества';

-- ---------------------------------------------------------------------------
-- Служебная таблица прогонов ETL: без неё «витрина обновлена» недоказуемо
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marts.etl_runs (
    run_id        BIGSERIAL PRIMARY KEY,
    mart_name     TEXT        NOT NULL,
    started_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at   TIMESTAMPTZ,
    rows_loaded   INTEGER,
    rows_rejected INTEGER     NOT NULL DEFAULT 0,
    status        TEXT        NOT NULL DEFAULT 'running',
    period_from   DATE,
    period_to     DATE,
    error_text    TEXT,
    CONSTRAINT ck_etl_runs_status CHECK (status IN ('running', 'ok', 'failed', 'partial'))
);

CREATE INDEX IF NOT EXISTS ix_etl_runs_mart_started ON marts.etl_runs (mart_name, started_at DESC);

-- ---------------------------------------------------------------------------
-- Измерения: минимально необходимые для витрин продаж и интеграций
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS marts.dim_date (
    date_key      DATE PRIMARY KEY,
    year          SMALLINT NOT NULL,
    quarter       SMALLINT NOT NULL,
    month         SMALLINT NOT NULL,
    day_of_month  SMALLINT NOT NULL,
    week_iso      SMALLINT NOT NULL,
    is_weekend    BOOLEAN  NOT NULL,
    month_name_ru TEXT     NOT NULL
);

INSERT INTO marts.dim_date (date_key, year, quarter, month, day_of_month, week_iso, is_weekend, month_name_ru)
SELECT
    d::date,
    EXTRACT(YEAR FROM d)::smallint,
    EXTRACT(QUARTER FROM d)::smallint,
    EXTRACT(MONTH FROM d)::smallint,
    EXTRACT(DAY FROM d)::smallint,
    EXTRACT(WEEK FROM d)::smallint,
    EXTRACT(ISODOW FROM d) IN (6, 7),
    CASE EXTRACT(MONTH FROM d)::int
        WHEN 1  THEN 'Январь'   WHEN 2  THEN 'Февраль'  WHEN 3  THEN 'Март'
        WHEN 4  THEN 'Апрель'   WHEN 5  THEN 'Май'      WHEN 6  THEN 'Июнь'
        WHEN 7  THEN 'Июль'     WHEN 8  THEN 'Август'   WHEN 9  THEN 'Сентябрь'
        WHEN 10 THEN 'Октябрь'  WHEN 11 THEN 'Ноябрь'   ELSE 'Декабрь'
    END
FROM generate_series(CURRENT_DATE - INTERVAL '3 years', CURRENT_DATE + INTERVAL '1 year', INTERVAL '1 day') AS d
ON CONFLICT (date_key) DO NOTHING;

CREATE TABLE IF NOT EXISTS marts.dim_store (
    store_key     INTEGER PRIMARY KEY,
    store_code    TEXT    NOT NULL UNIQUE,
    store_name    TEXT    NOT NULL,
    city          TEXT,
    format        TEXT,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    valid_from    DATE    NOT NULL DEFAULT DATE '2000-01-01',
    valid_to      DATE
);

COMMENT ON TABLE marts.dim_store IS 'Магазины и РЦ. Источник — справочник 1С «Подразделения»; SCD-тип 1 для атрибутов, срок действия — для истории';

CREATE TABLE IF NOT EXISTS marts.dim_product (
    product_key   BIGSERIAL PRIMARY KEY,
    sku           TEXT    NOT NULL UNIQUE,
    product_name  TEXT    NOT NULL,
    category      TEXT,
    brand         TEXT,
    is_weight     BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from    DATE    NOT NULL DEFAULT CURRENT_DATE,
    valid_to      DATE
);

CREATE TABLE IF NOT EXISTS marts.dim_counterparty (
    counterparty_key BIGSERIAL PRIMARY KEY,
    unp              TEXT    UNIQUE,
    name             TEXT    NOT NULL,
    kind             TEXT,
    is_personal_data BOOLEAN NOT NULL DEFAULT FALSE,
    valid_from       DATE    NOT NULL DEFAULT CURRENT_DATE
);

COMMENT ON COLUMN marts.dim_counterparty.is_personal_data IS 'Признак участия ПДн: для таких строк применяется маскирование в представлениях (task_208)';

-- ---------------------------------------------------------------------------
-- Учебные данные измерений: чтобы витрины не были пустыми на первом прогоне
-- ---------------------------------------------------------------------------
INSERT INTO marts.dim_store (store_key, store_code, store_name, city, format)
VALUES
    (1, 'MINSK-001', 'Евроопт Гурского 56', 'Минск',   'супермаркет'),
    (2, 'MINSK-002', 'Евроопт Немига 12',   'Минск',   'гипермаркет'),
    (3, 'BREST-001', 'Евроопт Брест Центр', 'Брест',   'супермаркет'),
    (4, 'GRODNO-001','Евроопт Гродно Юг',   'Гродно',  'дискаунтер'),
    (5, 'RC-MINSK',  'РЦ Минск',            'Минск',   'распределительный центр')
ON CONFLICT (store_key) DO NOTHING;

INSERT INTO marts.dim_product (sku, product_name, category, brand, is_weight)
VALUES
    ('SKU-00001', 'Молоко 2,5% 1л',        'Молочное',   'Учебный бренд', FALSE),
    ('SKU-00002', 'Хлеб «Нарочанский»',    'Бакалея',    'Хлебозавод 1',  FALSE),
    ('SKU-00003', 'Яблоки сезонные',       'Овощи/фрукты','-',            TRUE),
    ('SKU-00004', 'Средство для посуды 1л','Бытовая химия','Чистый дом',   FALSE),
    ('SKU-00005', 'Вода минеральная 1,5л', 'Напитки',    'Криница',       FALSE)
ON CONFLICT (sku) DO NOTHING;
