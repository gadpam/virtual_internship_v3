/* =============================================================================
   Назначение : выполнение FULL / DIFF / LOG бэкапов с фиксацией в журнале
   Задание    : task_193
   Тип        : СОЗДАЁТ ФАЙЛЫ КОПИЙ (данные ИБ не изменяет)
   Время      : FULL — минуты, LOG — секунды
   Риски      : место на диске; FULL в рабочее окно даёт нагрузку на диск
   Отмена     : удаление файлов копии (запись в журнале остаётся для аудита)
   ============================================================================= */

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @DatabaseName SYSNAME       = DB_NAME();
DECLARE @BackupRoot   NVARCHAR(500) = N'/var/opt/mssql/backup/rih';   -- Windows: N'D:\Backups\rih'
DECLARE @BackupType   NVARCHAR(10)  = 'LOG';                          -- FULL | DIFF | LOG
DECLARE @Compress     BIT           = 1;
DECLARE @Checksum     BIT           = 1;
DECLARE @DryRun       BIT           = 1;      -- 1 = только показать команду

DECLARE @Stamp    NVARCHAR(20)  = REPLACE(REPLACE(REPLACE(CONVERT(NVARCHAR(20), SYSUTCDATETIME(), 120),'-',''),':',''),' ','_');
DECLARE @FileName NVARCHAR(1000) = @BackupRoot + N'/' + @DatabaseName + N'_' + @BackupType + N'_' + @Stamp + N'.bak';
DECLARE @TypeCode NVARCHAR(20)  = CASE WHEN @BackupType = 'LOG' THEN N'LOG' ELSE N'DATABASE' END;

DECLARE @Sql NVARCHAR(MAX) =
      N'BACKUP ' + @TypeCode + N' ' + QUOTENAME(@DatabaseName)
    + N' TO DISK = N''' + @FileName + N''''
    + N' WITH INIT, FORMAT, STATS = 10'
    + CASE WHEN @Compress = 1 THEN N', COMPRESSION' ELSE N'' END
    + CASE WHEN @Checksum  = 1 THEN N', CHECKSUM'   ELSE N'' END
    + CASE WHEN @BackupType = 'LOG' THEN N'' ELSE N', NAME = N''' + @DatabaseName + N'-backup''' END
    + N';';

PRINT 'Команда бэкапа:';
PRINT @Sql;

IF @DryRun = 1
BEGIN
    PRINT 'DRY RUN: команда не выполнена. Проверьте путь и свободное место, затем установите @DryRun = 0.';
    RETURN;
END

DECLARE @LogId   BIGINT;
DECLARE @Started DATETIME2(3) = SYSUTCDATETIME();

INSERT INTO dbo.RIH_BackupLog (BackupType, DatabaseName, StartedAt, BackupFile)
VALUES (@BackupType, @DatabaseName, @Started, @FileName);
SET @LogId = SCOPE_IDENTITY();

BEGIN TRY
    EXEC sp_executesql @Sql;

    DECLARE @SizeMb DECIMAL(18,2);
    SELECT @SizeMb = CAST(h.backup_size / 1024.0 / 1024 AS DECIMAL(18,2))
    FROM msdb.dbo.backupset AS h
    WHERE h.database_name = @DatabaseName
    ORDER BY h.backup_finish_date DESC
    OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY;

    UPDATE dbo.RIH_BackupLog
    SET FinishedAt = SYSUTCDATETIME(),
        FileSizeMb = @SizeMb,
        ChecksumOk = @Checksum,
        Status     = 'ok'
    WHERE Id = @LogId;

    PRINT 'Бэкап выполнен: ' + @FileName;
END TRY
BEGIN CATCH
    UPDATE dbo.RIH_BackupLog
    SET FinishedAt = SYSUTCDATETIME(), Status = 'failed', ErrorText = ERROR_MESSAGE()
    WHERE Id = @LogId;
    PRINT 'ОШИБКА бэкапа: ' + ERROR_MESSAGE();
    THROW;
END CATCH

-- Кандидаты на удаление по политике хранения (удаляем файлы вручную, после проверки)
SELECT
    l.Id, l.BackupType, l.StartedAt, l.BackupFile, p.RetentionDays,
    CASE WHEN l.StartedAt < DATEADD(DAY, -p.RetentionDays, SYSUTCDATETIME())
         THEN 'кандидат на удаление' ELSE 'хранить' END AS [Решение]
FROM dbo.RIH_BackupLog AS l
JOIN dbo.RIH_BackupPolicy AS p ON p.BackupType = l.BackupType
WHERE l.Status = 'ok'
ORDER BY l.StartedAt;
