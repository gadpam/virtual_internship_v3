/* =============================================================================
   Назначение : репетиция восстановления на учебную базу + замер фактического RTO
   Задание    : task_194, task_264 (инструкция для коллег)
   Тип        : СОЗДАЁТ НОВУЮ БАЗУ; исходную не изменяет
   Время      : целевой RTO 30 минут; факт фиксируется в протоколе
   Риски      : место на диске, путаница имён (поэтому суффикс _restore_drill)
   Отмена     : DROP DATABASE учебной базы
   ============================================================================= */

SET NOCOUNT ON;
SET XACT_ABORT ON;

DECLARE @SourceDatabase SYSNAME       = DB_NAME();
DECLARE @TargetDatabase SYSNAME       = DB_NAME() + N'_restore_drill';
DECLARE @DryRun         BIT           = 1;
DECLARE @DrillStarted   DATETIME2(3)  = SYSUTCDATETIME();

PRINT '=== РЕПЕТИЦИЯ ВОССТАНОВЛЕНИЯ ===';
PRINT 'Источник : ' + @SourceDatabase;
PRINT 'Цель     : ' + @TargetDatabase;
PRINT 'Старт    : ' + CONVERT(NVARCHAR(30), @DrillStarted, 120);

-- 1. Цепочка копий: FULL → DIFF → LOG. copy_only в цепочку НЕ входит.
SELECT
    h.backup_finish_date                               AS [Завершено],
    CASE h.type WHEN 'D' THEN 'FULL' WHEN 'I' THEN 'DIFF' WHEN 'L' THEN 'LOG' END AS [Тип],
    CAST(h.backup_size / 1024.0 / 1024 AS DECIMAL(18,2)) AS [РазмерМБ],
    h.first_lsn                                        AS [FirstLsn],
    h.last_lsn                                         AS [LastLsn],
    h.is_copy_only                                     AS [ТолькоКопия],
    m.physical_device_name                             AS [Файл]
FROM msdb.dbo.backupset AS h
JOIN msdb.dbo.backupmediafamily AS m ON m.media_set_id = h.media_set_id
WHERE h.database_name = @SourceDatabase
  AND h.backup_finish_date >= DATEADD(DAY, -8, SYSUTCDATETIME())
  AND h.is_copy_only = 0
ORDER BY h.backup_finish_date;

IF @DryRun = 1
BEGIN
    PRINT 'DRY RUN: восстановление не выполняется.';
    PRINT 'Порядок команд (пути возьмите из результата запроса выше):';
    PRINT '  RESTORE DATABASE [' + @TargetDatabase + '] FROM DISK = N''<FULL.bak'''' WITH NORECOVERY, REPLACE,';
    PRINT '      MOVE ''<логическое имя данных>'' TO ''<путь .mdf>'',';
    PRINT '      MOVE ''<логическое имя журнала>'' TO ''<путь .ldf>'';';
    PRINT '  RESTORE DATABASE [' + @TargetDatabase + '] FROM DISK = N''<DIFF.bak>'' WITH NORECOVERY;';
    PRINT '  RESTORE LOG      [' + @TargetDatabase + '] FROM DISK = N''<LOG.bak>''  WITH NORECOVERY;   -- по цепочке LSN';
    PRINT '  RESTORE DATABASE [' + @TargetDatabase + '] WITH RECOVERY;';
    PRINT 'Логические имена файлов: RESTORE FILELISTONLY FROM DISK = N''<FULL.bak>'';';
    RETURN;
END

-- 2. Восстановление полной копии
DECLARE @Sql NVARCHAR(MAX);

SELECT @Sql = N'RESTORE DATABASE ' + QUOTENAME(@TargetDatabase)
            + N' FROM DISK = N''' + m.physical_device_name + N''''
            + N' WITH NORECOVERY, REPLACE;'
FROM msdb.dbo.backupset AS h
JOIN msdb.dbo.backupmediafamily AS m ON m.media_set_id = h.media_set_id
WHERE h.database_name = @SourceDatabase AND h.type = 'D' AND h.is_copy_only = 0
ORDER BY h.backup_finish_date DESC
OFFSET 0 ROWS FETCH NEXT 1 ROWS ONLY;

PRINT @Sql;
EXEC sp_executesql @Sql;

-- 3. Накат DIFF и LOG по цепочке в хронологическом порядке
DECLARE backup_cursor CURSOR LOCAL FAST_FORWARD FOR
    SELECT h.type, m.physical_device_name
    FROM msdb.dbo.backupset AS h
    JOIN msdb.dbo.backupmediafamily AS m ON m.media_set_id = h.media_set_id
    WHERE h.database_name = @SourceDatabase
      AND h.is_copy_only = 0
      AND h.backup_finish_date > (
          SELECT MAX(h2.backup_finish_date)
          FROM msdb.dbo.backupset AS h2
          WHERE h2.database_name = @SourceDatabase AND h2.type = 'D' AND h2.is_copy_only = 0)
    ORDER BY h.backup_finish_date;

DECLARE @Type NCHAR(1), @File NVARCHAR(1000);
OPEN backup_cursor;
FETCH NEXT FROM backup_cursor INTO @Type, @File;
WHILE @@FETCH_STATUS = 0
BEGIN
    SET @Sql = CASE WHEN @Type = 'L'
               THEN N'RESTORE LOG '      + QUOTENAME(@TargetDatabase) + N' FROM DISK = N''' + @File + N''' WITH NORECOVERY;'
               ELSE N'RESTORE DATABASE ' + QUOTENAME(@TargetDatabase) + N' FROM DISK = N''' + @File + N''' WITH NORECOVERY;'
               END;
    PRINT @Sql;
    EXEC sp_executesql @Sql;
    FETCH NEXT FROM backup_cursor INTO @Type, @File;
END
CLOSE backup_cursor;
DEALLOCATE backup_cursor;

SET @Sql = N'RESTORE DATABASE ' + QUOTENAME(@TargetDatabase) + N' WITH RECOVERY;';
PRINT @Sql;
EXEC sp_executesql @Sql;

-- 4. Протокол репетиции: фактический RTO против цели
DECLARE @DrillFinished DATETIME2(3) = SYSUTCDATETIME();
DECLARE @RtoMinutes DECIMAL(10,2)  = DATEDIFF(SECOND, @DrillStarted, @DrillFinished) / 60.0;

PRINT '=== ПРОТОКОЛ РЕПЕТИЦИИ ===';
PRINT 'Завершено    : ' + CONVERT(NVARCHAR(30), @DrillFinished, 120);
PRINT 'Факт RTO     : ' + CAST(@RtoMinutes AS NVARCHAR(20)) + ' мин';
PRINT 'Цель RTO     : 30 мин';
PRINT 'Соответствие : ' + CASE WHEN @RtoMinutes <= 30 THEN 'ДА' ELSE 'НЕТ — нужен разбор причин' END;

-- 5. Дымовые проверки восстановленной базы
EXEC (N'USE ' + QUOTENAME(@TargetDatabase) + N';
        SELECT COUNT(*) AS [Таблиц] FROM sys.tables;
        DBCC CHECKDB WITH NO_INFOMSGS, PHYSICAL_ONLY;');
