/* =============================================================================
   Назначение : сбор взаимоблокировок (deadlock) в читаемом виде
   Задание    : task_204
   Тип        : чтение системного журнала system_health; создаёт таблицу-журнал
   Время      : < 10 секунд
   ============================================================================= */

SET NOCOUNT ON;

-- 1. Журнал взаимоблокировок
IF OBJECT_ID('dbo.RIH_DeadlockLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RIH_DeadlockLog (
        Id           BIGINT IDENTITY(1,1) PRIMARY KEY,
        CapturedAt   DATETIME2(3)  NOT NULL DEFAULT SYSUTCDATETIME(),
        DeadlockTime DATETIME2(3)  NULL,
        VictimSpid   INT           NULL,
        Objects      NVARCHAR(2000) NULL,
        GraphXml     XML           NULL
    );
    CREATE INDEX IX_RIH_DeadlockLog_Time ON dbo.RIH_DeadlockLog (DeadlockTime DESC);
END

-- 2. Последние взаимоблокировки из ring buffer системного журнала
SELECT TOP (20)
    xed.value('@timestamp', 'datetime2(3)')          AS [Время],
    xed.value('(deadlock/victim-list/victimProcess/@id)[1]', 'varchar(50)') AS [Жертва],
    xed.value('(deadlock/process-list/process/@spid)[1]', 'int')            AS [SpidПервого],
    xed.query('.')                                   AS [ГрафБлокировкиXml]
FROM (
    SELECT CAST(target_data AS XML) AS target_xml
    FROM sys.dm_xe_session_targets AS st
    JOIN sys.dm_xe_sessions AS s ON s.address = st.event_session_address
    WHERE s.name = 'system_health' AND st.target_name = 'ring_buffer'
) AS data
CROSS APPLY data.target_xml.nodes('RingBufferTarget/event[@name="xml_deadlock_report"]') AS x(xed)
ORDER BY [Время] DESC;

-- 3. Какие объекты участвовали: сводка по повторам
SELECT
    obj.value('@objectname', 'nvarchar(500)')        AS [Объект],
    obj.value('@indexname',  'nvarchar(500)')        AS [Индекс],
    obj.value('@mode',       'nvarchar(50)')         AS [РежимБлокировки],
    COUNT(*)                                         AS [Случаев]
FROM (
    SELECT CAST(target_data AS XML) AS target_xml
    FROM sys.dm_xe_session_targets AS st
    JOIN sys.dm_xe_sessions AS s ON s.address = st.event_session_address
    WHERE s.name = 'system_health' AND st.target_name = 'ring_buffer'
) AS data
CROSS APPLY data.target_xml.nodes('RingBufferTarget/event[@name="xml_deadlock_report"]') AS x(xed)
CROSS APPLY xed.nodes('deadlock/resource-list/keylock/object, deadlock/resource-list/pagelock/object') AS o(obj)
GROUP BY obj.value('@objectname', 'nvarchar(500)'),
         obj.value('@indexname',  'nvarchar(500)'),
         obj.value('@mode',       'nvarchar(50)')
ORDER BY [Случаев] DESC;

/* Выводы для отчёта по task_204:
   1. Повторяется ли одна и та же пара объектов (типично: документ + регистр накопления)?
   2. Кто оказывается жертвой: фоновое задание или пользовательская сессия?
   3. Какое изменение снижает вероятность: порядок записи в проведении, уровень детализации блокировки,
      RCSI, вынос чтения из транзакции записи?
   4. Что проверено и что НЕ подтвердилось — отрицательные результаты тоже фиксируются.
*/
