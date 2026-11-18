-- =============================================================================
-- Словарь метрик: единое определение цифры (task_206, task_125)
-- Задание : task_206 (семантический слой), task_210 (SLA свежести)
-- Диалект : PostgreSQL
--
-- Зачем: «выручка» в отчёте коммерческого директора и «выручка» в отчёте
-- бухгалтера различаются. Пока определение живёт в головах — расхождение
-- объясняют «особенностями систем». Словарь делает расхождение ошибкой,
-- которую можно найти и исправить.
-- =============================================================================

CREATE TABLE IF NOT EXISTS marts.metrics_dictionary (
    metric_code   TEXT PRIMARY KEY,
    metric_name   TEXT NOT NULL,
    definition    TEXT NOT NULL,
    formula_sql   TEXT NOT NULL,
    source_table  TEXT NOT NULL,
    unit          TEXT NOT NULL,
    granularity   TEXT NOT NULL,
    owner_role    TEXT NOT NULL,
    slo_freshness TEXT,
    is_confidential BOOLEAN NOT NULL DEFAULT FALSE,
    status        TEXT NOT NULL DEFAULT 'active',
    approved_at   DATE,
    notes         TEXT,
    CONSTRAINT ck_metrics_status CHECK (status IN ('active', 'draft', 'deprecated'))
);

COMMENT ON TABLE marts.metrics_dictionary IS 'Единственный источник определений метрик. Новая метрика в дашборде появляется только после записи сюда (правило из task_206).';

INSERT INTO marts.metrics_dictionary
    (metric_code, metric_name, definition, formula_sql, source_table, unit, granularity, owner_role, slo_freshness, is_confidential, status, approved_at, notes)
VALUES
    ('M-001', 'Выручка розничная',
     'Сумма проданного товара за вычетом скидок, без НДС не выделяется; каналы offline и online',
     'SUM(f.revenue)',
     'marts.fact_sales', 'BYN', 'день / магазин / канал',
     'Коммерческий директор', 'T+1 до 06:00', FALSE, 'active', CURRENT_DATE,
     'Расхождение с бухгалтерской выручкой объясняется моментом признания: здесь — факт продажи, в БП — отгруженное и закрытие периода'),

    ('M-002', 'Валовая прибыль',
     'Выручка минус себестоимость по данным учёта на момент продажи',
     'SUM(f.revenue) - SUM(f.cost)',
     'marts.fact_sales', 'BYN', 'день / магазин',
     'Финансовый аналитик', 'T+1 до 06:00', FALSE, 'active', CURRENT_DATE,
     'Себестоимость пересчитывается при закрытии месяца: метрика за прошлые периоды может измениться'),

    ('M-003', 'Маржинальность',
     'Доля валовой прибыли в выручке, %',
     'ROUND(100.0 * (SUM(f.revenue) - SUM(f.cost)) / NULLIF(SUM(f.revenue), 0), 2)',
     'marts.fact_sales', '%', 'день / магазин / категория',
     'Коммерческий директор', 'T+1 до 06:00', FALSE, 'active', CURRENT_DATE, NULL),

    ('M-004', 'Средний чек (строка)',
     'Средняя выручка на строку продажи; используется как прокси среднего чека при отсутствии номера чека',
     'ROUND(SUM(f.revenue) / NULLIF(COUNT(*), 0), 2)',
     'marts.fact_sales', 'BYN', 'день / магазин',
     'Аналитик розницы', 'T+1 до 06:00', FALSE, 'draft', NULL,
     'Требует уточнения: настоящий средний чек считается по doc_number, а не по строкам'),

    ('M-005', 'Доступность интеграции',
     'Доля успешных обращений к системе-партнёру, %',
     'ROUND(100.0 * SUM(CASE WHEN status = ''success'' THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 3)',
     'marts.fact_integration', '%', 'день / система / операция',
     'Дежурный инженер RIH', '15 минут', FALSE, 'active', CURRENT_DATE,
     'SLO 99,5% за 30 дней; совпадает с алертом RIHIntegrationDown'),

    ('M-006', 'p95 длительности интеграции',
     '95-й перцентиль длительности обращений, секунды',
     'ROUND(percentile_cont(0.95) WITHIN GROUP (ORDER BY duration_ms) / 1000.0, 3)',
     'marts.fact_integration', 'с', 'день / система / операция',
     'Дежурный инженер RIH', '15 минут', FALSE, 'active', CURRENT_DATE,
     'SLO 2 секунды (task_271)'),

    ('M-007', 'Отставание обмена',
     'Разница между текущим временем и временем последнего успешного обмена по плану, секунды',
     'MAX(EXTRACT(EPOCH FROM (now() - last_success_at)))',
     'staging.exchange_status', 'с', 'план обмена / направление',
     'Владелец интеграции', '5 минут', FALSE, 'active', CURRENT_DATE,
     'Порог алерта 900 секунд'),

    ('M-008', 'Число инцидентов интеграций',
     'Количество созданных инцидентов за период, включая автоматически созданные из DLQ',
     'COUNT(*)',
     'staging.incidents', 'шт', 'день / система',
     'Дежурный инженер RIH', '1 час', FALSE, 'active', CURRENT_DATE, NULL),

    ('M-009', 'Доля записей с ошибками качества',
     'Процент строк источника, не прошедших правила качества данных',
     'ROUND(100.0 * SUM(CASE WHEN is_valid = FALSE THEN 1 ELSE 0 END) / NULLIF(COUNT(*), 0), 2)',
     'staging.dq_results', '%', 'день / источник / правило',
     'Владелец данных НСИ', 'T+1 до 07:00', FALSE, 'active', CURRENT_DATE,
     'Порог принятия решения о блокировке загрузки — 5% (task_212)'),

    ('M-010', 'Начисленные бонусы',
     'Сумма баллов, начисленных по программе лояльности за продажи',
     'SUM(f.bonus_accrued)',
     'marts.fact_sales', 'баллы', 'день / магазин',
     'Владелец программы лояльности', 'T+1 до 06:00', TRUE, 'active', CURRENT_DATE,
     'Конфиденциально: содержит данные клиентов, в self-service доступна только агрегированно (task_208)')
ON CONFLICT (metric_code) DO UPDATE
SET metric_name   = EXCLUDED.metric_name,
    definition    = EXCLUDED.definition,
    formula_sql   = EXCLUDED.formula_sql,
    source_table  = EXCLUDED.source_table,
    unit          = EXCLUDED.unit,
    granularity   = EXCLUDED.granularity,
    owner_role    = EXCLUDED.owner_role,
    slo_freshness = EXCLUDED.slo_freshness,
    is_confidential = EXCLUDED.is_confidential,
    status        = EXCLUDED.status,
    approved_at   = EXCLUDED.approved_at,
    notes         = EXCLUDED.notes;

-- Представление для аналитиков: что можно брать и как это считается
CREATE OR REPLACE VIEW marts.v_metrics_dictionary AS
SELECT
    metric_code      AS "Код",
    metric_name      AS "Метрика",
    definition       AS "Определение",
    unit             AS "Единица",
    granularity      AS "Детализация",
    owner_role       AS "Владелец",
    slo_freshness    AS "SLA свежести",
    is_confidential  AS "Конфиденциально",
    status           AS "Статус",
    notes            AS "Примечание"
FROM marts.metrics_dictionary
WHERE status <> 'deprecated'
ORDER BY metric_code;
