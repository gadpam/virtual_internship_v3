/* =============================================================================
   Назначение : «кто активен» — сессии, ожидания, запросы, планы
   Задание    : task_184, task_204
   Тип        : только чтение (последний блок — опционально KILL, по умолчанию выключен)
   Время      : < 10 секунд
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 1. Активные пользовательские сессии с текстом запроса и ожиданием
SELECT
    r.session_id                                     AS [Сессия],
    r.status                                         AS [Статус],
    r.command                                        AS [Команда],
    r.wait_type                                      AS [ТипОжидания],
    r.wait_time                                      AS [ОжиданиеМс],
    r.blocking_session_id                            AS [БлокируетСессия],
    r.cpu_time                                       AS [CpuМс],
    r.total_elapsed_time                             AS [ПрошлоМс],
    r.reads                                          AS [Чтений],
    r.writes                                         AS [Записей],
    r.logical_reads                                  AS [ЛогическихЧтений],
    r.row_count                                      AS [Строк],
    DATEDIFF(SECOND, r.start_time, SYSUTCDATETIME()) AS [ДлитсяСек],
    s.login_name                                     AS [Пользователь],
    s.host_name                                      AS [Хост],
    s.program_name                                   AS [Программа],
    DB_NAME(r.database_id)                           AS [База],
    SUBSTRING(txt.text,
              (r.statement_start_offset / 2) + 1,
              (CASE WHEN r.statement_end_offset = -1 THEN DATALENGTH(txt.text)
                    ELSE r.statement_end_offset END - r.statement_start_offset) / 2 + 1
    )                                                AS [ТекущийЗапрос]
FROM sys.dm_exec_requests AS r
JOIN sys.dm_exec_sessions AS s ON s.session_id = r.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) AS txt
WHERE r.session_id <> @@SPID
  AND s.is_user_process = 1
ORDER BY r.total_elapsed_time DESC;

-- 2. Топ ожиданий сервера (сброс статистики: DBCC SQLPERF('sys.dm_os_wait_stats', CLEAR))
SELECT TOP (25)
    w.wait_type                                      AS [Ожидание],
    w.waiting_tasks_count                            AS [Случаев],
    CAST(w.wait_time_ms / 1000.0 AS DECIMAL(18,2))    AS [Секунд],
    CAST(100.0 * w.wait_time_ms
         / NULLIF(SUM(w.wait_time_ms) OVER (), 0) AS DECIMAL(5,2)) AS [ДоляPct],
    CAST(w.max_wait_time_ms / 1000.0 AS DECIMAL(18,2)) AS [МаксимумСек],
    CASE
        WHEN w.wait_type LIKE 'LCK_%'            THEN 'блокировки: ищите голову цепочки (020_blocking_chain.sql)'
        WHEN w.wait_type LIKE 'PAGEIOLATCH%'     THEN 'диск: чтение с диска, не хватает кеша или индекса'
        WHEN w.wait_type LIKE 'PAGELATCH%'       THEN 'горячая страница в памяти (часто tempdb или последний лист индекса)'
        WHEN w.wait_type IN ('CXPACKET','CXCONSUMER','EXECSYNC') THEN 'параллелизм: проверьте MAXDOP и cost threshold'
        WHEN w.wait_type = 'ASYNC_NETWORK_IO'    THEN 'клиент не забирает результат: проблема в потреблении, а не в запросе'
        WHEN w.wait_type LIKE 'SOS_SCHEDULER%'   THEN 'не хватает CPU'
        WHEN w.wait_type = 'WRITELOG'            THEN 'журнал транзакций: много мелких записей или медленный диск'
        WHEN w.wait_type IN ('SLEEP_TASK','BROKER_TASK_STOP','WAITFOR','REQUEST_FOR_DEADLOCK_SEARCH',
                             'HADR_FILESTREAM_IOMGR_IOCOMPLETION','XE_TIMER_EVENT','XE_DISPATCHER_WAIT',
                             'BROKER_EVENTHANDLER','BROKER_RECEIVE_WAITFOR','LAZYWRITER_SLEEP',
                             'SQLTRACE_INCREMENTAL_FLUSH_SLEEP','CHECKPOINT_QUEUE','LOGMGR_QUEUE')
             THEN 'фоновое ожидание платформы — можно игнорировать'
        ELSE 'требует разбора'
    END                                              AS [Интерпретация]
FROM sys.dm_os_wait_stats AS w
WHERE w.waiting_tasks_count > 0
ORDER BY w.wait_time_ms DESC;

-- 3. Снимок нагрузки: память, CPU, блокировки
SELECT
    (SELECT cntr_value FROM sys.dm_os_performance_counters
      WHERE counter_name = 'Page life expectancy' AND object_name LIKE '%Buffer Manager%') AS [PLEСек],
    (SELECT cntr_value FROM sys.dm_os_performance_counters
      WHERE counter_name = 'Batch Requests/sec')                                           AS [ПакетовВСек],
    (SELECT cntr_value FROM sys.dm_os_performance_counters
      WHERE counter_name = 'User Connections')                                             AS [Соединений],
    (SELECT COUNT(*) FROM sys.dm_exec_requests WHERE status = 'runnable')                  AS [ГотовыКВыполнению],
    (SELECT COUNT(*) FROM sys.dm_exec_requests WHERE blocking_session_id <> 0)             AS [Заблокировано],
    (SELECT physical_memory_in_use_kb / 1024 FROM sys.dm_os_process_memory)                AS [ПамятьПроцессаМБ];

-- Признаки нехватки ресурсов:
--   PLE < 300 секунд при большом объёме памяти → не хватает буферного пула;
--   «ГотовыКВыполнению» долго > 0              → не хватает CPU;
--   «Заблокировано» > 5                        → разбор цепочки блокировок.

-- 4. ОПАСНО: снятие сессии. По умолчанию ничего не делаем.
DECLARE @KillSessionId INT = 0;
IF @KillSessionId > 50
BEGIN
    PRINT 'Для снятия сессии выполните вручную: KILL ' + CAST(@KillSessionId AS VARCHAR(10));
    PRINT 'Перед этим сохраните текст запроса, план и время — иначе расследование не воспроизвести.';
END
