/* =============================================================================
   Назначение : проверка читаемости резервных копий и сводка готовности
   Задание    : task_193
   Тип        : только чтение (RESTORE VERIFYONLY базу не восстанавливает)
   Время      : минуты для больших FULL-копий
   Примечание : VERIFYONLY проверяет структуру копии, но НЕ гарантирует успех
                восстановления. Гарантия — только репетиция (030_restore_rehearsal.sql).
   ============================================================================= */

SET NOCOUNT ON;

-- 1. Журнал копий за неделю с признаками проверок
SELECT
    l.Id                                             AS [IdЖурнала],
    l.BackupType                                     AS [Тип],
    l.StartedAt                                      AS [Начало],
    l.DurationSec                                    AS [ДлительностьСек],
    l.FileSizeMb                                     AS [РазмерМБ],
    l.ChecksumOk                                     AS [Checksum],
    l.VerifyOnlyOk                                   AS [VerifyOnly],
    l.StoredOffsite                                  AS [ВнеПлощадки],
    l.Status                                         AS [Статус],
    l.BackupFile                                     AS [Файл]
FROM dbo.RIH_BackupLog AS l
WHERE l.StartedAt >= DATEADD(DAY, -7, SYSUTCDATETIME())
ORDER BY l.StartedAt DESC;

-- 2. Команда проверки последней полной копии
DECLARE @LastFull NVARCHAR(1000);
SELECT TOP (1) @LastFull = m.physical_device_name
FROM msdb.dbo.backupset AS h
JOIN msdb.dbo.backupmediafamily AS m ON m.media_set_id = h.media_set_id
WHERE h.database_name = DB_NAME() AND h.type = 'D'
ORDER BY h.backup_finish_date DESC;

IF @LastFull IS NULL
    PRINT 'Полных копий не найдено — проверьте, что бэкапы вообще выполняются.';
ELSE
BEGIN
    PRINT 'Последняя полная копия: ' + @LastFull;
    PRINT N'RESTORE VERIFYONLY FROM DISK = N''' + @LastFull + N''' WITH CHECKSUM;';
    PRINT N'RESTORE HEADERONLY FROM DISK = N''' + @LastFull + N''';';
    PRINT 'Раскомментируйте EXEC ниже, чтобы выполнить проверку на своём стенде.';
    -- EXEC sp_executesql N'RESTORE VERIFYONLY FROM DISK = N''' + @LastFull + N''' WITH CHECKSUM;';
END

-- 3. Целостность текущей базы
PRINT 'Проверка целостности (окно обслуживания):';
PRINT '  DBCC CHECKDB (''' + DB_NAME() + ''') WITH NO_INFOMSGS, PHYSICAL_ONLY;';
PRINT '  Раз в неделю — полная проверка без PHYSICAL_ONLY.';

-- 4. Сводка «мы защищены?» — четыре числа для отчёта руководителю
SELECT
    (SELECT MAX(StartedAt) FROM dbo.RIH_BackupLog
      WHERE BackupType = 'FULL' AND Status = 'ok')                   AS [ПоследнийFull],
    (SELECT MAX(StartedAt) FROM dbo.RIH_BackupLog
      WHERE BackupType = 'LOG'  AND Status = 'ok')                   AS [ПоследнийLog],
    (SELECT COUNT(*) FROM dbo.RIH_BackupLog
      WHERE Status = 'failed'
        AND StartedAt >= DATEADD(DAY, -7, SYSUTCDATETIME()))         AS [ОшибокЗаНеделю],
    (SELECT COUNT(*) FROM dbo.RIH_BackupLog
      WHERE StoredOffsite = 0 AND Status = 'ok'
        AND StartedAt >= DATEADD(DAY, -7, SYSUTCDATETIME()))         AS [БезВнешнейКопии],
    CASE
        WHEN (SELECT COUNT(*) FROM dbo.RIH_BackupLog WHERE Status = 'ok') = 0
            THEN 'НЕТ: копий не делали'
        WHEN (SELECT COUNT(*) FROM dbo.RIH_BackupLog WHERE StoredOffsite = 1 AND Status = 'ok') = 0
            THEN 'ЧАСТИЧНО: все копии на одной площадке'
        ELSE 'ДА, при условии успешной репетиции восстановления'
    END                                                              AS [Вывод];
