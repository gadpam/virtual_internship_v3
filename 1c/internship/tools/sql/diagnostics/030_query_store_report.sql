/* =============================================================================
   Назначение : Query Store — регрессии планов и «подорожавшие» запросы
   Задание    : task_187, task_190
   Тип        : чтение; включение Query Store меняет настройки БД (блок 1, вручную)
   Время      : < 30 секунд
   ============================================================================= */

SET NOCOUNT ON;

-- 1. Включён ли Query Store
SELECT
    name                            AS [База],
    is_query_store_on               AS [QueryStoreВключен],
    query_store_capture_policy_desc AS [ПолитикаСбора]
FROM sys.databases
WHERE name = DB_NAME();

IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = DB_NAME() AND is_query_store_on = 1)
BEGIN
    PRINT 'Query Store выключен. Для включения (нужны права ALTER DATABASE):';
    PRINT '  ALTER DATABASE [' + DB_NAME() + '] SET QUERY_STORE = ON;';
    PRINT '  ALTER DATABASE [' + DB_NAME() + '] SET QUERY_STORE (OPERATION_MODE = READ_WRITE,';
    PRINT '      CLEANUP_POLICY = (STALE_QUERY_THRESHOLD_DAYS = 30),';
    PRINT '      DATA_FLUSH_INTERVAL_SECONDS = 900, INTERVAL_LENGTH_MINUTES = 30,';
    PRINT '      MAX_STORAGE_SIZE_MB = 1024, QUERY_CAPTURE_MODE = AUTO);';
END

-- 2. Топ запросов по суммарной длительности за 24 часа
SELECT TOP (25)
    q.query_id                                       AS [QueryId],
    SUM(rs.count_executions)                         AS [Выполнений],
    CAST(SUM(rs.count_executions * rs.avg_duration) / 1000000.0 AS DECIMAL(18,2)) AS [СуммарноСек],
    CAST(AVG(rs.avg_duration) / 1000.0 AS DECIMAL(18,2))   AS [СреднееМс],
    CAST(MAX(rs.max_duration) / 1000.0 AS DECIMAL(18,2))   AS [МаксимумМс],
    CAST(AVG(rs.stdev_duration) / 1000.0 AS DECIMAL(18,2)) AS [СтдОтклМс],
    SUM(rs.count_physical_io_reads)                  AS [ФизЧтений],
    COUNT(DISTINCT rs.plan_id)                       AS [РазныхПланов],
    LEFT(qt.query_sql_text, 300)                     AS [Текст]
FROM sys.query_store_runtime_stats AS rs
JOIN sys.query_store_plan AS p          ON p.plan_id = rs.plan_id
JOIN sys.query_store_query AS q         ON q.query_id = p.query_id
JOIN sys.query_store_query_text AS qt   ON qt.query_text_id = q.query_text_id
JOIN sys.query_store_runtime_stats_interval AS ri
     ON ri.runtime_stats_interval_id = rs.runtime_stats_interval_id
WHERE ri.start_time >= DATEADD(HOUR, -24, SYSUTCDATETIME())
GROUP BY q.query_id, qt.query_sql_text
ORDER BY [СуммарноСек] DESC;

-- 3. Запросы с несколькими планами и большим разбросом длительности (parameter sniffing)
SELECT TOP (15)
    q.query_id                                       AS [QueryId],
    COUNT(DISTINCT rs.plan_id)                       AS [Планов],
    CAST(MIN(rs.avg_duration) / 1000.0 AS DECIMAL(18,2)) AS [МинимумМс],
    CAST(MAX(rs.avg_duration) / 1000.0 AS DECIMAL(18,2)) AS [МаксимумМс],
    CAST(MAX(rs.avg_duration) / NULLIF(MIN(rs.avg_duration),0) AS DECIMAL(18,1)) AS [Разброс],
    LEFT(qt.query_sql_text, 200)                     AS [Текст]
FROM sys.query_store_runtime_stats AS rs
JOIN sys.query_store_plan AS p  ON p.plan_id = rs.plan_id
JOIN sys.query_store_query AS q ON q.query_id = p.query_id
JOIN sys.query_store_query_text AS qt ON qt.query_text_id = q.query_text_id
GROUP BY q.query_id, qt.query_sql_text
HAVING COUNT(DISTINCT rs.plan_id) > 1
   AND MAX(rs.avg_duration) > 5 * NULLIF(MIN(rs.avg_duration), 0)
ORDER BY [Разброс] DESC;

-- 4. Форсированные планы и ошибки форсирования
SELECT
    p.query_id                                       AS [QueryId],
    p.plan_id                                        AS [PlanId],
    p.is_forced_plan                                 AS [Форсирован],
    p.force_failure_count                            AS [ОшибокФорсирования],
    p.last_force_failure_reason_desc                 AS [ПричинаОшибки],
    LEFT(qt.query_sql_text, 200)                     AS [Текст]
FROM sys.query_store_plan AS p
JOIN sys.query_store_query AS q       ON q.query_id = p.query_id
JOIN sys.query_store_query_text AS qt ON qt.query_text_id = q.query_text_id
WHERE p.is_forced_plan = 1;

/* Что делать с результатом (task_187):
   - большой разброс планов → OPTIMIZE FOR / план-гид / форсирование плана;
   - много физических чтений при малом результате → не хватает индекса (ADR, task_188);
   - среднее «в норме», а стд. отклонение большое → ищите пиковые часы и фоновые задания.
*/
