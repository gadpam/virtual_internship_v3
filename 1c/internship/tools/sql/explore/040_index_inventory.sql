/* =============================================================================
   Назначение : инвентаризация индексов ключевых таблиц
   Задание    : task_181, подготовка к task_188 (ADR по индексу)
   Тип        : только чтение
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

SELECT
    SCHEMA_NAME(t.schema_id)                         AS [Схема],
    t.name                                           AS [Таблица],
    i.name                                           AS [Индекс],
    i.type_desc                                      AS [Тип],
    i.is_unique                                      AS [Уникальный],
    i.is_primary_key                                 AS [PK],
    i.has_filter                                     AS [Фильтрованный],
    i.filter_definition                              AS [УсловиеФильтра],
    STUFF((
        SELECT ', ' + c.name + CASE WHEN ic.is_descending_key = 1 THEN ' DESC' ELSE '' END
        FROM sys.index_columns AS ic
        JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 0
        ORDER BY ic.key_ordinal
        FOR XML PATH('')
    ), 1, 2, '')                                     AS [КлючевыеКолонки],
    STUFF((
        SELECT ', ' + c.name
        FROM sys.index_columns AS ic
        JOIN sys.columns AS c ON c.object_id = ic.object_id AND c.column_id = ic.column_id
        WHERE ic.object_id = i.object_id AND ic.index_id = i.index_id AND ic.is_included_column = 1
        FOR XML PATH('')
    ), 1, 2, '')                                     AS [ВключённыеКолонки],
    ps.row_count                                     AS [Строк],
    CAST(ps.used_page_count * 8.0 / 1024 AS DECIMAL(18,2)) AS [РазмерМБ]
FROM sys.indexes AS i
JOIN sys.tables AS t          ON t.object_id = i.object_id
LEFT JOIN sys.dm_db_partition_stats AS ps
       ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.type > 0
  AND t.is_ms_shipped = 0
  AND t.name IN (
      -- подставьте сюда свои «горячие» таблицы из 030_top_tables_by_size.sql
      SELECT TOP (20) t2.name
      FROM sys.tables AS t2
      JOIN sys.dm_db_partition_stats AS p2 ON p2.object_id = t2.object_id
      ORDER BY p2.row_count DESC
  )
ORDER BY [Таблица], i.index_id;
