/* =============================================================================
   Назначение : топ таблиц по занятому месту — где живут большие данные
   Задание    : task_181, task_215 (планирование архивирования)
   Тип        : только чтение
   Время      : 10–60 секунд на большой базе
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

;WITH sizes AS (
    SELECT
        t.object_id,
        SCHEMA_NAME(t.schema_id)                                    AS schema_name,
        t.name                                                      AS table_name,
        SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END)   AS row_count,
        SUM(a.total_pages) * 8.0 / 1024                             AS total_mb,
        SUM(a.used_pages)  * 8.0 / 1024                             AS used_mb,
        SUM(CASE WHEN i.index_id > 1 THEN a.total_pages ELSE 0 END) * 8.0 / 1024 AS index_mb
    FROM sys.tables AS t
    JOIN sys.indexes AS i       ON i.object_id = t.object_id
    JOIN sys.partitions AS p    ON p.object_id = i.object_id AND p.index_id = i.index_id
    JOIN sys.allocation_units AS a ON a.container_id = p.partition_id
    WHERE t.is_ms_shipped = 0 AND i.object_id > 255
    GROUP BY t.object_id, SCHEMA_NAME(t.schema_id), t.name
)
SELECT TOP (50)
    schema_name                                     AS [Схема],
    table_name                                      AS [Таблица],
    row_count                                       AS [Строк],
    CAST(total_mb AS DECIMAL(18,2))                  AS [ВсегоМБ],
    CAST(used_mb  AS DECIMAL(18,2))                  AS [ЗанятоМБ],
    CAST(index_mb AS DECIMAL(18,2))                  AS [ИндексыМБ],
    CAST(CASE WHEN row_count > 0 THEN index_mb * 1024.0 / row_count ELSE 0 END
         AS DECIMAL(18,2))                           AS [БайтИндексаНаСтроку],
    CASE
        WHEN table_name LIKE '\_InfoR%'     ESCAPE '\' THEN 'регистр сведений — кандидат на партиционирование/архив'
        WHEN table_name LIKE '\_AccumR%'    ESCAPE '\' THEN 'регистр накопления — проверьте итоги'
        WHEN table_name LIKE '\_ChngR%'     ESCAPE '\' THEN 'регистр изменений — очистка после обменов'
        WHEN table_name LIKE '\_Ftable%'    ESCAPE '\' THEN 'хранилище файлов — внешний перенос'
        ELSE 'уточнить назначение'
    END                                             AS [Комментарий]
FROM sizes
ORDER BY total_mb DESC;
