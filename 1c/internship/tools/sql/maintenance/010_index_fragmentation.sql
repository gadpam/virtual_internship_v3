/* =============================================================================
   Назначение : фрагментация индексов и генерация команд обслуживания
   Задание    : task_195
   Тип        : чтение + (опционально) выполнение сгенерированных команд
   Время      : 1–10 минут на большой базе
   Примечание : @Execute = 0 — только список команд (безопасно).
                Обслуживание выполняйте в окно низкой нагрузки.
   ============================================================================= */

SET NOCOUNT ON;

DECLARE @DatabaseName SYSNAME      = DB_NAME();
DECLARE @MinPageCount INT          = 1000;   -- маленькие индексы не трогаем
DECLARE @ReorgThreshold FLOAT      = 5.0;
DECLARE @RebuildThreshold FLOAT    = 30.0;
DECLARE @Execute BIT               = 0;      -- 1 = выполнять команды

;WITH frag AS (
    SELECT
        s.object_id,
        s.index_id,
        OBJECT_SCHEMA_NAME(s.object_id)      AS schema_name,
        OBJECT_NAME(s.object_id)             AS table_name,
        i.name                               AS index_name,
        i.type_desc                          AS index_type,
        s.page_count,
        s.avg_fragmentation_in_percent,
        s.fragment_count,
        ps.used_page_count * 8.0 / 1024      AS size_mb
    FROM sys.dm_db_index_physical_stats(
             DB_ID(@DatabaseName), NULL, NULL, NULL, 'LIMITED') AS s
    JOIN sys.indexes AS i
         ON i.object_id = s.object_id AND i.index_id = s.index_id
    LEFT JOIN sys.dm_db_partition_stats AS ps
         ON ps.object_id = s.object_id AND ps.index_id = s.index_id
    WHERE s.page_count >= @MinPageCount
      AND i.name IS NOT NULL
      AND i.type IN (1, 2)                    -- clustered / nonclustered
)
SELECT
    schema_name                              AS [Схема],
    table_name                               AS [Таблица],
    index_name                               AS [Индекс],
    index_type                               AS [Тип],
    page_count                               AS [Страниц],
    CAST(size_mb AS DECIMAL(18,2))            AS [РазмерМБ],
    CAST(avg_fragmentation_in_percent AS DECIMAL(6,2)) AS [ФрагментацияPct],
    fragment_count                           AS [Фрагментов],
    CASE
        WHEN avg_fragmentation_in_percent >= @RebuildThreshold THEN 'REBUILD'
        WHEN avg_fragmentation_in_percent >= @ReorgThreshold   THEN 'REORGANIZE'
        ELSE 'SKIP'
    END                                      AS [Действие],
    CASE
        WHEN avg_fragmentation_in_percent >= @RebuildThreshold
        THEN 'ALTER INDEX ' + QUOTENAME(index_name) + ' ON '
             + QUOTENAME(schema_name) + '.' + QUOTENAME(table_name)
             + ' REBUILD WITH (ONLINE = ON, SORT_IN_TEMPDB = ON, MAXDOP = 4);'
        WHEN avg_fragmentation_in_percent >= @ReorgThreshold
        THEN 'ALTER INDEX ' + QUOTENAME(index_name) + ' ON '
             + QUOTENAME(schema_name) + '.' + QUOTENAME(table_name)
             + ' REORGANIZE;'
        ELSE '-- пропуск: фрагментация ниже порога'
    END                                      AS [Команда]
FROM frag
ORDER BY avg_fragmentation_in_percent DESC;

-- Обновление статистики по таблицам с большим числом изменений (task_195)
SELECT
    OBJECT_SCHEMA_NAME(s.object_id)          AS [Схема],
    OBJECT_NAME(s.object_id)                 AS [Таблица],
    st.name                                  AS [Статистика],
    st.stats_id                              AS [Id],
    sp.last_updated                          AS [Обновлена],
    sp.rows                                  AS [Строк],
    sp.rows_sampled                          AS [СтрокВВыборке],
    CAST(100.0 * sp.rows_sampled / NULLIF(sp.rows,0) AS DECIMAL(5,1)) AS [ВыборкаPct],
    sp.modification_counter                  AS [ИзмененийСОбновления],
    CAST(100.0 * sp.modification_counter / NULLIF(sp.rows,0) AS DECIMAL(6,2)) AS [ИзмененоPct],
    CASE WHEN sp.modification_counter * 1.0 / NULLIF(sp.rows,0) > 0.10
         THEN 'UPDATE STATISTICS ' + QUOTENAME(OBJECT_SCHEMA_NAME(s.object_id))
              + '.' + QUOTENAME(OBJECT_NAME(s.object_id))
              + '(' + QUOTENAME(st.name) + ') WITH FULLSCAN;'
         ELSE '-- актуальна'
    END                                      AS [Команда]
FROM sys.stats AS st
JOIN sys.stats_columns AS sc ON sc.object_id = st.object_id AND sc.stats_id = st.stats_id
JOIN sys.columns AS c        ON c.object_id = sc.object_id AND c.column_id = sc.column_id
JOIN sys.objects AS o        ON o.object_id = st.object_id
CROSS APPLY sys.dm_db_stats_properties(st.object_id, st.stats_id) AS sp
JOIN sys.tables AS s         ON s.object_id = st.object_id
WHERE o.is_ms_shipped = 0
  AND sp.rows > 1000
ORDER BY [ИзмененоPct] DESC;

IF @Execute = 1
BEGIN
    PRINT 'Выполнение команд обслуживания включено. В учебном стенде снимите комментарий'
          + ' и запускайте команды построчно — так видно эффект каждой.';
END
