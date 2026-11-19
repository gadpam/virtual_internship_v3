/* =============================================================================
   Назначение : ШАБЛОН безопасного изменения данных (task_183)
   Задание    : task_183, используется в task_216 и task_269
   Тип        : ИЗМЕНЯЕТ ДАННЫЕ — по умолчанию в режиме DRY RUN
   Время      : зависит от объёма; всегда проверяйте план beforehand
   Отмена     : ROLLBACK до COMMIT; после COMMIT — только из резервной копии

   ПРАВИЛА:
     1. Сначала SELECT с тем же предикатом — убедиться, что строки те самые.
     2. DRY RUN = 1 → только считаем, ничего не меняем.
     3. Изменение внутри явной транзакции, с журналом «до/после».
     4. Ограничение пакетом (TOP + цикл), чтобы не держать долгую блокировку.
     5. После выполнения — проверка ожидаемого числа строк.
   ============================================================================= */

SET NOCOUNT ON;
SET XACT_ABORT ON;                    -- любая ошибка откатывает транзакцию целиком
SET TRANSACTION ISOLATION LEVEL READ COMMITTED;

DECLARE @DryRun       BIT          = 1;      -- 1 = ничего не меняем
DECLARE @BatchSize    INT          = 5000;   -- строк за один пакет
DECLARE @MaxRows      INT          = 100000; -- страховка от «обновить всю таблицу»
DECLARE @ExpectedRows INT;
DECLARE @Processed    INT = 0;

-- Журнал операции: кто, когда, что, сколько. Таблица создаётся один раз.
IF OBJECT_ID('dbo.RIH_ChangeLog', 'U') IS NULL
BEGIN
    CREATE TABLE dbo.RIH_ChangeLog (
        Id           BIGINT IDENTITY(1,1) PRIMARY KEY,
        ScriptName   NVARCHAR(200)  NOT NULL,
        StartedAt    DATETIME2(3)   NOT NULL DEFAULT SYSUTCDATETIME(),
        FinishedAt   DATETIME2(3)   NULL,
        RowsAffected INT            NULL,
        DryRun       BIT            NOT NULL,
        ExecutedBy   NVARCHAR(128)  NOT NULL DEFAULT SUSER_SNAME(),
        Comment      NVARCHAR(1000) NULL
    );
END

-- 1. Оцениваем объём ДО изменения
SELECT @ExpectedRows = COUNT(*)
FROM dbo.TargetTable            -- <<< замените на свою таблицу
WHERE Status = 'draft'          -- <<< замените на свой предикат
  AND ModifiedAt < DATEADD(MONTH, -12, SYSUTCDATETIME());

PRINT 'Найдено строк для изменения: ' + CAST(@ExpectedRows AS VARCHAR(20));

IF @ExpectedRows > @MaxRows
BEGIN
    RAISERROR('Объём больше страховочного лимита %d — уменьшите выборку или согласуйте операцию.', 16, 1, @MaxRows);
    RETURN;
END

IF @DryRun = 1
BEGIN
    INSERT INTO dbo.RIH_ChangeLog (ScriptName, FinishedAt, RowsAffected, DryRun, Comment)
    VALUES ('030_safe_update_template.sql', SYSUTCDATETIME(), @ExpectedRows, 1, 'DRY RUN: оценка объёма');

    SELECT TOP (20) * FROM dbo.TargetTable
    WHERE Status = 'draft'
      AND ModifiedAt < DATEADD(MONTH, -12, SYSUTCDATETIME());

    PRINT 'DRY RUN завершён. Для реального выполнения установите @DryRun = 0.';
    RETURN;
END

-- 2. Реальное изменение пакетами
DECLARE @Batch INT = 1;
BEGIN TRY
    BEGIN TRAN;

    WHILE @Processed < @ExpectedRows
    BEGIN
        UPDATE TOP (@BatchSize) t
        SET t.Status     = 'archived',
            t.ModifiedAt = SYSUTCDATETIME()
        FROM dbo.TargetTable AS t
        WHERE t.Status = 'draft'
          AND t.ModifiedAt < DATEADD(MONTH, -12, SYSUTCDATETIME());

        SET @Processed += @@ROWCOUNT;
        PRINT 'Пакет ' + CAST(@Batch AS VARCHAR(5)) + ': обработано строк '
              + CAST(@@ROWCOUNT AS VARCHAR(10)) + ', всего ' + CAST(@Processed AS VARCHAR(10));
        SET @Batch += 1;

        IF @@ROWCOUNT = 0 BREAK;
        WAITFOR DELAY '00:00:00.200';   -- даём серверу «вздохнуть» между пакетами
    END

    IF @Processed <> @ExpectedRows
    BEGIN
        RAISERROR('Ожидали %d строк, обработано %d — откатываем.', 16, 1, @ExpectedRows, @Processed);
    END

    COMMIT;

    INSERT INTO dbo.RIH_ChangeLog (ScriptName, FinishedAt, RowsAffected, DryRun, Comment)
    VALUES ('030_safe_update_template.sql', SYSUTCDATETIME(), @Processed, 0, 'успешно');

    PRINT 'Готово: изменено строк ' + CAST(@Processed AS VARCHAR(10));
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK;
    INSERT INTO dbo.RIH_ChangeLog (ScriptName, FinishedAt, RowsAffected, DryRun, Comment)
    VALUES ('030_safe_update_template.sql', SYSUTCDATETIME(), @Processed, 0,
            'ОШИБКА: ' + ERROR_MESSAGE());
    THROW;
END CATCH
