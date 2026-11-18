/* =============================================================================
   Назначение : диагностика tempdb и журнала транзакций
   Задание    : task_185, используется в расследовании task_204
   Тип        : только чтение
   Время      : < 10 секунд
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 1. tempdb: размер, свободно, кто занял
SELECT
    f.name                                           AS [Файл],
    CAST(f.size * 8.0 / 1024 AS DECIMAL(18,2))        AS [РазмерМБ],
    CAST((f.size - FILEPROPERTY(f.name,'SpaceUsed')) * 8.0 / 1024 AS DECIMAL(18,2)) AS [СвободноМБ],
    CAST(100.0 * FILEPROPERTY(f.name,'SpaceUsed') / NULLIF(f.size,0) AS DECIMAL(5,1)) AS [ЗанятоPct]
FROM tempdb.sys.database_files AS f
WHERE f.type = 0;

SELECT TOP (20)
    t.session_id,
    su.user_objects_alloc_page_count * 8 / 1024      AS [ПользовательскиеМБ],
    su.internal_objects_alloc_page_count * 8 / 1024  AS [ВнутренниеМБ],
    (su.user_objects_alloc_page_count + su.internal_objects_alloc_page_count) * 8 / 1024 AS [ВсегоМБ],
    txt.text                                         AS [ТекстЗапроса]
FROM tempdb.sys.dm_db_session_space_usage AS su
JOIN sys.dm_exec_sessions AS t ON t.session_id = su.session_id
OUTER APPLY sys.dm_exec_sql_text(t.most_recent_sql_handle) AS txt
WHERE su.session_id > 50
ORDER BY [ВсегоМБ] DESC;

-- 2. Журнал транзакций: размер и причина, почему он не уссекается
SELECT
    d.name                                           AS [База],
    d.recovery_model_desc                            AS [РежимВосстановления],
    d.log_reuse_wait_desc                            AS [ПочемуЖурналНеУсекается],
    CAST(ls.total_log_size_in_bytes  / 1024.0 / 1024 AS DECIMAL(18,2)) AS [ЖурналМБ],
    CAST(ls.used_log_space_in_bytes  / 1024.0 / 1024 AS DECIMAL(18,2)) AS [ЗанятоМБ],
    CAST(ls.used_log_space_in_percent AS DECIMAL(5,1)) AS [ЗанятоPct]
FROM sys.dm_db_log_stats(DB_ID()) AS ls
CROSS JOIN sys.databases AS d
WHERE d.database_id = DB_ID();

-- Расшифровка log_reuse_wait_desc для отчёта:
--   NOTHING              — усекать нечего, всё в норме
--   LOG_BACKUP           — ждём резервную копию журнала (делайте бэкап LOG чаще)
--   ACTIVE_TRANSACTION   — длинная транзакция держит журнал (ищите её ниже)
--   CHECKPOINT           — ждём контрольную точку
--   AVAILABILITY_REPLICA — влияние группы доступности

-- 3. Самая долгая открытая транзакция — типичная причина раздувшегося журнала
SELECT TOP (10)
    st.session_id                                    AS [Сессия],
    at.transaction_id                                AS [IdТранзакции],
    DATEDIFF(SECOND, at.transaction_begin_time, SYSUTCDATETIME()) AS [ДлитсяСек],
    at.transaction_begin_time                        AS [Начата],
    txt.text                                         AS [ТекстЗапроса],
    s.login_name                                     AS [Пользователь],
    s.host_name                                      AS [Хост],
    s.program_name                                   AS [Программа]
FROM sys.dm_tran_active_transactions AS at
JOIN sys.dm_tran_session_transactions AS st ON st.transaction_id = at.transaction_id
JOIN sys.dm_exec_sessions AS s              ON s.session_id = st.session_id
OUTER APPLY sys.dm_exec_sql_text(s.most_recent_sql_handle) AS txt
WHERE at.transaction_type IN (1, 2, 3)
ORDER BY [ДлитсяСек] DESC;
