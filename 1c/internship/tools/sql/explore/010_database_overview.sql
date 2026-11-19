/* =============================================================================
   Назначение : общая картина базы данных учебного стенда RIH
   Задание    : task_181
   Автор      : стажёр RIH
   Тип        : только чтение, безопасно на любом стенде
   Время      : < 5 секунд
   Риски      : нет
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;   -- исследование не должно блокировать запись

-- 1. Параметры базы: имя, режим восстановления, collation, состояние
SELECT
    d.database_id,
    d.name                                        AS [База],
    d.recovery_model_desc                         AS [РежимВосстановления],
    d.collation_name                              AS [Collation],
    d.state_desc                                  AS [Состояние],
    d.compatibility_level                         AS [УровеньСовместимости],
    d.is_read_committed_snapshot_on               AS [RCSI],   -- важно для блокировок (task_184)
    DATABASEPROPERTYEX(d.name, 'Updateability')   AS [Доступность]
FROM sys.databases AS d
WHERE d.name = DB_NAME();

-- 2. Файлы данных и журнала: размер, занятое место, автоприрост
SELECT
    f.name                                        AS [ЛогическоеИмя],
    f.physical_name                               AS [Путь],
    f.type_desc                                   AS [Тип],
    CAST(f.size * 8.0 / 1024 AS DECIMAL(18,2))     AS [РазмерМБ],
    CAST(FILEPROPERTY(f.name, 'SpaceUsed') * 8.0 / 1024 AS DECIMAL(18,2)) AS [ЗанятоМБ],
    CASE WHEN f.is_percent_growth = 1
         THEN CAST(f.growth AS VARCHAR(10)) + '%'
         ELSE CAST(f.growth * 8.0 / 1024 AS VARCHAR(10)) + ' МБ'
    END                                           AS [Автоприрост],
    f.max_size                                    AS [Максимум]
FROM sys.database_files AS f
ORDER BY f.type, f.name;

-- 3. Итог по базе: данные / журнал / всего
SELECT
    SUM(CASE WHEN type = 0 THEN size ELSE 0 END) * 8.0 / 1024 / 1024 AS [ДанныеГБ],
    SUM(CASE WHEN type = 1 THEN size ELSE 0 END) * 8.0 / 1024 / 1024 AS [ЖурналГБ],
    SUM(size) * 8.0 / 1024 / 1024                                    AS [ВсегоГБ]
FROM sys.database_files;

-- 4. Число таблиц и индексов: масштаб схемы
SELECT
    (SELECT COUNT(*) FROM sys.tables)                        AS [Таблиц],
    (SELECT COUNT(*) FROM sys.indexes WHERE index_id > 0)    AS [Индексов],
    (SELECT COUNT(*) FROM sys.procedures)                    AS [Процедур],
    (SELECT COUNT(*) FROM sys.views)                         AS [Представлений];
