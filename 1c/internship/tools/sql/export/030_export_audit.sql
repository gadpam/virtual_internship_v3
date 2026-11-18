-- =============================================================================
-- Журнал выгрузок: кто, что, кому, на каком основании (task_124, task_291)
-- Диалект : PostgreSQL
-- =============================================================================

CREATE TABLE IF NOT EXISTS staging.export_audit (
    export_id      BIGSERIAL PRIMARY KEY,
    export_code    TEXT        NOT NULL,
    exported_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    format         TEXT        NOT NULL CHECK (format IN ('csv', 'json', 'xml', 'xlsx', 'parquet')),
    target         TEXT        NOT NULL,           -- кому передано: роль, система, контрагент
    legal_basis    TEXT,                           -- основание передачи (договор, согласие, служебная необходимость)
    contains_pd    BOOLEAN     NOT NULL DEFAULT FALSE,
    masked         BOOLEAN     NOT NULL DEFAULT FALSE,
    rows_exported  INTEGER,
    checksum       TEXT,
    file_name      TEXT,
    purpose        TEXT        NOT NULL,
    requested_by   TEXT        NOT NULL,
    approved_by    TEXT,
    retention_days INTEGER     NOT NULL DEFAULT 90
);

CREATE INDEX IF NOT EXISTS ix_export_audit_date ON staging.export_audit (exported_at DESC);
CREATE INDEX IF NOT EXISTS ix_export_audit_pd   ON staging.export_audit (exported_at DESC) WHERE contains_pd;

COMMENT ON TABLE staging.export_audit IS
    'Реестр выгрузок. Записи с contains_pd = TRUE попадают в отчёт по ПДн (task_291); выгрузка без legal_basis запрещена.';

-- 1. Выгрузки за 30 дней
SELECT
    exported_at                                        AS "Когда",
    export_code                                        AS "Код",
    format                                             AS "Формат",
    target                                             AS "Кому",
    rows_exported                                      AS "Строк",
    contains_pd                                        AS "ПДн",
    masked                                             AS "Маскировано",
    requested_by                                       AS "Запросил",
    approved_by                                        AS "Согласовал",
    purpose                                            AS "Цель"
FROM staging.export_audit
WHERE exported_at >= now() - INTERVAL '30 days'
ORDER BY exported_at DESC;

-- 2. Нарушения политики: ПДн без основания или без маскирования
SELECT
    export_id                                          AS "Id",
    exported_at                                        AS "Когда",
    export_code                                        AS "Код",
    target                                             AS "Кому",
    CASE
        WHEN contains_pd AND (legal_basis IS NULL OR legal_basis = '') THEN 'ПДн без основания'
        WHEN contains_pd AND NOT masked                               THEN 'ПДн без маскирования'
        WHEN approved_by IS NULL                                      THEN 'нет согласования'
        ELSE 'ок'
    END                                                AS "Нарушение"
FROM staging.export_audit
WHERE contains_pd OR approved_by IS NULL
ORDER BY exported_at DESC;

-- 3. Сводка для отчёта по ПДн (task_291)
SELECT
    date_trunc('day', exported_at)                     AS "День",
    COUNT(*)                                           AS "Выгрузок",
    SUM(CASE WHEN contains_pd THEN 1 ELSE 0 END)       AS "С ПДн",
    SUM(CASE WHEN contains_pd AND NOT masked THEN 1 ELSE 0 END) AS "ПДн без маски",
    COUNT(DISTINCT target)                             AS "Получателей"
FROM staging.export_audit
WHERE exported_at >= now() - INTERVAL '30 days'
GROUP BY 1
ORDER BY 1 DESC;
