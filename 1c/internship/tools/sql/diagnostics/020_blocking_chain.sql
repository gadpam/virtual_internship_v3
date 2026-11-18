/* =============================================================================
   Назначение : цепочки блокировок — кто держит, кто ждёт, на каком ресурсе
   Задание    : task_184, task_204
   Тип        : только чтение
   Время      : < 5 секунд
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 1. Головы цепочек блокировок: сами никем не заблокированы, но держат других
SELECT
    r.session_id                                     AS [ГоловаЦепочки],
    r.status                                         AS [Статус],
    r.command                                        AS [Команда],
    r.wait_type                                      AS [Ожидание],
    DATEDIFF(SECOND, r.start_time, SYSUTCDATETIME()) AS [ДлитсяСек],
    s.login_name                                     AS [Пользователь],
    s.host_name                                      AS [Хост],
    s.program_name                                   AS [Программа],
    txt.text                                         AS [ЗапросГоловы],
    (SELECT COUNT(*) FROM sys.dm_exec_requests AS w
      WHERE w.blocking_session_id = r.session_id)    AS [ЖдутНапрямую]
FROM sys.dm_exec_requests AS r
JOIN sys.dm_exec_sessions AS s ON s.session_id = r.session_id
CROSS APPLY sys.dm_exec_sql_text(r.sql_handle) AS txt
WHERE r.blocking_session_id = 0
  AND r.session_id IN (SELECT blocking_session_id FROM sys.dm_exec_requests WHERE blocking_session_id <> 0)
ORDER BY [ЖдутНапрямую] DESC;

-- 2. Карта «ждёт → блокирует» с ресурсом и текстами обоих запросов
SELECT
    wt.blocking_session_id                           AS [Блокирует],
    r.session_id                                     AS [Ждёт],
    r.wait_type                                      AS [ТипОжидания],
    r.wait_time                                      AS [ЖдётМс],
    r.command                                        AS [КомандаЖдущего],
    tl.resource_type                                 AS [Ресурс],
    tl.request_mode                                  AS [ЗапрошенРежим],
    tl.request_status                                AS [СтатусЗапроса],
    CASE tl.resource_type
        WHEN 'OBJECT' THEN OBJECT_NAME(tl.resource_associated_entity_id)
        ELSE CAST(tl.resource_associated_entity_id AS VARCHAR(50))
    END                                              AS [Объект],
    SUBSTRING(wtxt.text, 1, 500)                     AS [ЗапросЖдущего],
    SUBSTRING(btxt.text, 1, 500)                     AS [ЗапросБлокирующего]
FROM sys.dm_os_waiting_tasks AS wt
JOIN sys.dm_exec_requests AS r     ON r.session_id = wt.session_id
LEFT JOIN sys.dm_tran_locks AS tl  ON tl.request_session_id = wt.blocking_session_id
LEFT JOIN sys.dm_exec_sessions AS bs ON bs.session_id = wt.blocking_session_id
OUTER APPLY sys.dm_exec_sql_text(r.sql_handle) AS wtxt
OUTER APPLY sys.dm_exec_sql_text(bs.most_recent_sql_handle) AS btxt
ORDER BY r.wait_time DESC;

-- 3. Распределение блокировок по объектам: где «горячо»
SELECT TOP (30)
    OBJECT_NAME(tl.resource_associated_entity_id)    AS [Объект],
    tl.resource_type                                 AS [ТипРесурса],
    tl.request_mode                                  AS [Режим],
    COUNT(*)                                         AS [Блокировок]
FROM sys.dm_tran_locks AS tl
WHERE tl.resource_type = 'OBJECT'
  AND tl.resource_database_id = DB_ID()
GROUP BY OBJECT_NAME(tl.resource_associated_entity_id), tl.resource_type, tl.request_mode
ORDER BY [Блокировок] DESC;

-- 4. Транзакции дольше 30 секунд — будущие блокировки
SELECT
    at.transaction_id                                AS [IdТранзакции],
    st.session_id                                    AS [Сессия],
    at.name                                          AS [Имя],
    DATEDIFF(SECOND, at.transaction_begin_time, SYSUTCDATETIME()) AS [ДлитсяСек],
    s.login_name                                     AS [Пользователь],
    s.program_name                                   AS [Программа]
FROM sys.dm_tran_active_transactions AS at
JOIN sys.dm_tran_session_transactions AS st ON st.transaction_id = at.transaction_id
JOIN sys.dm_exec_sessions AS s ON s.session_id = st.session_id
WHERE DATEDIFF(SECOND, at.transaction_begin_time, SYSUTCDATETIME()) > 30
ORDER BY [ДлитсяСек] DESC;

/* Выводы для отчёта:
   - есть ли длинная транзакция из 1С (обычно «Проведение» с большим числом движений);
   - блокируется ли таблица целиком (эскалация блокировок) или отдельные строки;
   - помогает ли в этом сценарии READ_COMMITTED_SNAPSHOT ON (см. task_204).
*/
