/* =============================================================================
   Назначение : журнал и шаблон еженедельного плана обслуживания СУБД
   Задание    : task_195
   Тип        : создаёт служебные таблицы, данные не меняет
   Время      : < 5 секунд на создание, обслуживание — по расписанию
   ============================================================================= */

SET NOCOUNT ON;

-- 1. Журнал обслуживания: без него «мы обслуживаем базу» — необоснованное утверждение
IF OBJECT_ID('dbo.RIH_MaintenanceLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RIH_MaintenanceLog (
        Id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        TaskName       NVARCHAR(100) NOT NULL,   -- Reindex / UpdateStats / CheckDb / Backup / Cleanup
        ObjectName     NVARCHAR(300) NULL,
        StartedAt      DATETIME2(3)  NOT NULL DEFAULT SYSUTCDATETIME(),
        FinishedAt     DATETIME2(3)  NULL,
        DurationSec    AS (DATEDIFF(SECOND, StartedAt, FinishedAt)),
        RowsAffected   INT           NULL,
        Status         NVARCHAR(20)  NOT NULL DEFAULT 'running',  -- running / ok / failed / skipped
        ErrorText      NVARCHAR(2000) NULL,
        ExecutedBy     NVARCHAR(128) NOT NULL DEFAULT SUSER_SNAME()
    );
    CREATE INDEX IX_RIH_MaintenanceLog_Started ON dbo.RIH_MaintenanceLog (StartedAt DESC);
END

-- 2. План обслуживания: что, когда, каким окном
IF OBJECT_ID('dbo.RIH_MaintenancePlan', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RIH_MaintenancePlan (
        Id             INT IDENTITY(1,1) PRIMARY KEY,
        TaskName       NVARCHAR(100) NOT NULL,
        Schedule       NVARCHAR(50)  NOT NULL,   -- daily 02:00 / weekly Sun 01:00 / monthly
        WindowMinutes  INT           NOT NULL,   -- сколько времени мы готовы отдать
        BlockingLevel  NVARCHAR(20)  NOT NULL DEFAULT 'online',  -- online / offline / readonly
        OwnerRole      NVARCHAR(50)  NOT NULL,   -- DBA / 1C-инженер / дежурный
        Notes          NVARCHAR(1000) NULL
    );

    INSERT INTO dbo.RIH_MaintenancePlan (TaskName, Schedule, WindowMinutes, BlockingLevel, OwnerRole, Notes)
    VALUES
      ('UpdateStats',    'daily 02:00',      30,  'online',   'DBA',        'FULLSCAN по горячим таблицам, SAMPLED по остальным'),
      ('Reindex',        'weekly Sun 01:00', 120, 'online',   'DBA',        'REBUILD > 30%, REORGANIZE 5-30%, пропуск < 5%'),
      ('CheckDb',        'weekly Sun 04:00', 90,  'readonly', 'DBA',        'PHYSICAL_ONLY в будни, полная проверка раз в неделю'),
      ('BackupFull',     'daily 23:00',      60,  'online',   'DBA',        'RPO 24 часа по полным, 15 минут по журналу'),
      ('BackupLog',      'every 15 min',     5,   'online',   'DBA',        'не даёт журналу расти бесконечно'),
      ('CleanupChngR',   'daily 03:00',      20,  'offline',  '1C-инженер', 'очистка регистров изменений после завершённых обменов'),
      ('TempdbReport',   'daily 08:00',      5,   'readonly', 'дежурный',   'снимок использования tempdb для отчёта'),
      ('ArchiveOldData', 'monthly 1st 02:00',240, 'offline',  '1C-инженер', 'архив периодов старше 3 лет по согласованному списку');
END

-- 3. Текущее состояние плана: что просрочено
SELECT
    p.TaskName                               AS [Задача],
    p.Schedule                               AS [Расписание],
    p.WindowMinutes                          AS [ОкноМин],
    p.OwnerRole                              AS [Ответственный],
    MAX(l.FinishedAt)                        AS [ПоследнийУспех],
    DATEDIFF(HOUR, MAX(l.FinishedAt), SYSUTCDATETIME()) AS [ЧасовНазад],
    CASE
        WHEN MAX(l.FinishedAt) IS NULL THEN 'НИ РАЗУ НЕ ВЫПОЛНЯЛОСЬ'
        WHEN MAX(l.FinishedAt) < DATEADD(DAY, -8, SYSUTCDATETIME()) THEN 'просрочено'
        ELSE 'в норме'
    END                                      AS [Статус]
FROM dbo.RIH_MaintenancePlan AS p
LEFT JOIN dbo.RIH_MaintenanceLog AS l
       ON l.TaskName = p.TaskName AND l.Status = 'ok'
GROUP BY p.TaskName, p.Schedule, p.WindowMinutes, p.OwnerRole
ORDER BY [Статус] DESC, [ЧасовНазад] DESC;
