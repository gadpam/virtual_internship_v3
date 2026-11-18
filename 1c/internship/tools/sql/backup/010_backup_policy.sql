/* =============================================================================
   Назначение : план резервного копирования и журнал копий стенда RIH
   Задание    : task_193
   Тип        : создаёт служебные таблицы, данные ИБ не меняет
   Время      : < 5 секунд
   ============================================================================= */

SET NOCOUNT ON;

-- 1. Журнал копий: без него RPO — это предположение
IF OBJECT_ID('dbo.RIH_BackupLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RIH_BackupLog (
        Id             BIGINT IDENTITY(1,1) PRIMARY KEY,
        BackupType     NVARCHAR(10) NOT NULL,       -- FULL / DIFF / LOG
        DatabaseName   SYSNAME      NOT NULL,
        StartedAt      DATETIME2(3) NOT NULL DEFAULT SYSUTCDATETIME(),
        FinishedAt     DATETIME2(3) NULL,
        DurationSec    AS (DATEDIFF(SECOND, StartedAt, FinishedAt)),
        FileSizeMb     DECIMAL(18,2) NULL,
        BackupFile     NVARCHAR(1000) NULL,
        ChecksumOk     BIT          NULL,
        VerifyOnlyOk   BIT          NULL,
        StoredOffsite  BIT          NOT NULL DEFAULT 0,
        Status         NVARCHAR(20) NOT NULL DEFAULT 'running',  -- running / ok / failed
        ErrorText      NVARCHAR(2000) NULL,
        ExecutedBy     NVARCHAR(128) NOT NULL DEFAULT SUSER_SNAME()
    );
    CREATE INDEX IX_RIH_BackupLog_Type_Date ON dbo.RIH_BackupLog (DatabaseName, BackupType, StartedAt DESC);
END

-- 2. Политика: что, когда, сколько храним
IF OBJECT_ID('dbo.RIH_BackupPolicy', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RIH_BackupPolicy (
        Id               INT IDENTITY(1,1) PRIMARY KEY,
        BackupType       NVARCHAR(10) NOT NULL,
        Schedule         NVARCHAR(50) NOT NULL,
        RetentionDays    INT          NOT NULL,
        OffsiteCopy      BIT          NOT NULL DEFAULT 1,
        TargetRpoMinutes INT          NOT NULL,
        TargetRtoMinutes INT          NOT NULL,
        Notes            NVARCHAR(1000) NULL
    );

    INSERT INTO dbo.RIH_BackupPolicy (BackupType, Schedule, RetentionDays, OffsiteCopy, TargetRpoMinutes, TargetRtoMinutes, Notes)
    VALUES
      ('FULL', 'daily 23:00',      14, 1, 1440, 60, 'полная копия; основа цепочки восстановления'),
      ('DIFF', 'every 6 hours',     7, 1,  360, 30, 'ускоряет восстановление между полными'),
      ('LOG',  'every 15 minutes',  3, 1,   15, 15, 'определяет фактический RPO 15 минут');
END

-- 3. Соответствие фактических копий политике: где провалы
SELECT
    p.BackupType                                     AS [Тип],
    p.Schedule                                       AS [Расписание],
    p.RetentionDays                                  AS [ХранениеДней],
    p.TargetRpoMinutes                               AS [ЦельRpoМин],
    ISNULL(f.LastBackup, 'НИКОГДА')                  AS [ПоследняяКопия],
    DATEDIFF(MINUTE, f.LastBackup, SYSUTCDATETIME()) AS [МинутНазад],
    f.CountRecent                                    AS [КопийЗаПериод],
    CASE
        WHEN f.LastBackup IS NULL THEN 'КРИТИЧНО: копий нет'
        WHEN p.BackupType = 'LOG'  AND DATEDIFF(MINUTE, f.LastBackup, SYSUTCDATETIME()) > p.TargetRpoMinutes * 2 THEN 'превышен RPO'
        WHEN p.BackupType = 'FULL' AND DATEDIFF(HOUR,  f.LastBackup, SYSUTCDATETIME()) > 30 THEN 'просрочена полная копия'
        WHEN p.BackupType = 'DIFF' AND DATEDIFF(HOUR,  f.LastBackup, SYSUTCDATETIME()) > 14 THEN 'просрочена разностная копия'
        ELSE 'в норме'
    END                                              AS [Статус]
FROM dbo.RIH_BackupPolicy AS p
OUTER APPLY (
    SELECT MAX(l.StartedAt) AS LastBackup, COUNT(*) AS CountRecent
    FROM dbo.RIH_BackupLog AS l
    WHERE l.BackupType = p.BackupType
      AND l.Status = 'ok'
      AND l.StartedAt >= DATEADD(DAY, -p.RetentionDays, SYSUTCDATETIME())
) AS f
ORDER BY [Статус] DESC;

-- 4. Что знает сам SQL Server о копиях (msdb) — сверка с нашим журналом
SELECT TOP (20)
    h.database_name                                  AS [База],
    CASE h.type WHEN 'D' THEN 'FULL' WHEN 'I' THEN 'DIFF' WHEN 'L' THEN 'LOG' END AS [Тип],
    h.backup_start_date                              AS [Начало],
    h.backup_finish_date                             AS [Конец],
    CAST(h.backup_size / 1024.0 / 1024 AS DECIMAL(18,2))          AS [РазмерМБ],
    CAST(h.compressed_backup_size / 1024.0 / 1024 AS DECIMAL(18,2)) AS [СжатыйМБ],
    h.is_copy_only                                   AS [ТолькоКопия],
    m.physical_device_name                           AS [Файл]
FROM msdb.dbo.backupset AS h
JOIN msdb.dbo.backupmediafamily AS m ON m.media_set_id = h.media_set_id
WHERE h.database_name = DB_NAME()
ORDER BY h.backup_start_date DESC;
