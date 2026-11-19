-- =============================================================================
-- Витрина интеграций: marts.fact_integration
-- Задание : task_205, task_271 (SLI/SLO поверх SQL, а не только Prometheus)
-- Диалект : PostgreSQL
-- Источник: регистр сведений 1С «РИХ_ЖурналИнтеграций», выгрузка по расписанию
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.fact_integration (
    event_id        BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    occurred_at     TIMESTAMPTZ NOT NULL,
    date_key        DATE        NOT NULL REFERENCES marts.dim_date (date_key),
    system_code     TEXT        NOT NULL,     -- shop | loyalty | tk | bank | tracker | ai | edo
    operation       TEXT        NOT NULL,     -- orders.import | stock.export | accrue | ...
    direction       TEXT        NOT NULL,     -- inbound | outbound
    status          TEXT        NOT NULL,     -- success | error | timeout | duplicate
    http_code       INTEGER,
    duration_ms     INTEGER     NOT NULL DEFAULT 0,
    correlation_id  TEXT,
    incident_ref    TEXT,
    error_code      TEXT,
    retry_count     SMALLINT    NOT NULL DEFAULT 0,
    loaded_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT ck_fact_integration_direction CHECK (direction IN ('inbound', 'outbound')),
    CONSTRAINT ck_fact_integration_duration  CHECK (duration_ms >= 0),
    UNIQUE (system_code, operation, correlation_id, occurred_at)
);

COMMENT ON TABLE marts.fact_integration IS
    'Журнал интеграционных обращений. SLI считаются отсюда (v_sli_integration), поэтому формула должна совпадать с Prometheus: расхождение между источниками — признак ошибки выгрузки.';

CREATE INDEX IF NOT EXISTS ix_fact_integration_date_system ON marts.fact_integration (date_key, system_code);
CREATE INDEX IF NOT EXISTS ix_fact_integration_status      ON marts.fact_integration (status, occurred_at DESC);
CREATE INDEX IF NOT EXISTS ix_fact_integration_correlation ON marts.fact_integration (correlation_id);

-- ---------------------------------------------------------------------------
-- SLI/SLO: те же пороги, что в tools/ci/observability/alert_rules.yml
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW marts.v_sli_integration AS
SELECT
    f.date_key,
    f.system_code,
    f.operation,
    COUNT(*)                                                                AS requests_total,
    SUM(CASE WHEN f.status = 'success'  THEN 1 ELSE 0 END)                   AS requests_ok,
    SUM(CASE WHEN f.status <> 'success' THEN 1 ELSE 0 END)                   AS requests_failed,
    ROUND(100.0 * SUM(CASE WHEN f.status = 'success' THEN 1 ELSE 0 END)
          / NULLIF(COUNT(*), 0), 3)                                          AS availability_pct,
    ROUND((percentile_cont(0.50) WITHIN GROUP (ORDER BY f.duration_ms) / 1000.0)::numeric, 3) AS p50_seconds,
    ROUND((percentile_cont(0.95) WITHIN GROUP (ORDER BY f.duration_ms) / 1000.0)::numeric, 3) AS p95_seconds,
    ROUND((percentile_cont(0.99) WITHIN GROUP (ORDER BY f.duration_ms) / 1000.0)::numeric, 3) AS p99_seconds,
    SUM(CASE WHEN f.status = 'duplicate' THEN 1 ELSE 0 END)                  AS duplicates,
    SUM(f.retry_count)                                                       AS retries_total,
    (100.0 * SUM(CASE WHEN f.status = 'success' THEN 1 ELSE 0 END)
     / NULLIF(COUNT(*), 0)) >= 99.5                                          AS availability_slo_met,
    (percentile_cont(0.95) WITHIN GROUP (ORDER BY f.duration_ms) / 1000.0) <= 2.0 AS latency_slo_met
FROM marts.fact_integration AS f
GROUP BY f.date_key, f.system_code, f.operation;

COMMENT ON VIEW marts.v_sli_integration IS 'SLI интеграций по дням и системам. SLO: доступность >= 99,5%, p95 <= 2 с (task_271).';

-- ---------------------------------------------------------------------------
-- Учебные данные: смесь успешных и ошибочных обращений, включая медленные
-- ---------------------------------------------------------------------------
INSERT INTO marts.fact_integration
    (occurred_at, date_key, system_code, operation, direction, status, http_code, duration_ms, correlation_id, error_code, retry_count)
SELECT
    ts,
    ts::date,
    sys.code,
    op.name,
    op.direction,
    CASE
        WHEN random() < 0.90 THEN 'success'
        WHEN random() < 0.05 THEN 'timeout'
        WHEN random() < 0.03 THEN 'duplicate'
        ELSE 'error'
    END,
    CASE WHEN random() < 0.90 THEN 200 WHEN random() < 0.5 THEN 500 ELSE 429 END,
    (50 + random() * CASE WHEN random() < 0.05 THEN 5000 ELSE 800 END)::int,
    md5(random()::text || ts::text),
    CASE WHEN random() < 0.9 THEN NULL ELSE 'PARTNER_UNAVAILABLE' END,
    (random() < 0.2)::int
FROM generate_series(CURRENT_DATE - 30, CURRENT_DATE, INTERVAL '30 minutes') AS ts
CROSS JOIN (VALUES ('shop'), ('loyalty'), ('tk'), ('bank')) AS sys(code)
CROSS JOIN (VALUES ('orders.import', 'inbound'), ('stock.export', 'outbound')) AS op(name, direction);

ANALYZE marts.fact_integration;
