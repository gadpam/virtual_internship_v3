/* =============================================================================
   Назначение : «горячие» таблицы — что читают и пишут чаще всего
   Задание    : task_190, вход для task_188 (ADR по индексу)
   Тип        : только чтение, данные сбрасываются при перезапуске службы SQL Server
   Время      : < 10 секунд
   Примечание : снимайте показатели ПОСЛЕ представительной нагрузки, иначе
                картина будет отражать только служебную активность.
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 1. Операции пользовательского ввода-вывода по таблицам
SELECT TOP (30)
    OBJECT_SCHEMA_NAME(s.object_id)                    AS [Схема],
    OBJECT_NAME(s.object_id)                           AS [Таблица],
    s.user_seeks                                       AS [Поисков],
    s.user_scans                                       AS [Сканирований],
    s.user_lookups                                     AS [Lookup],
    s.user_updates                                     AS [Обновлений],
    s.user_seeks + s.user_scans + s.user_lookups       AS [ЧтенийВсего],
    CAST(100.0 * s.user_scans
         / NULLIF(s.user_seeks + s.user_scans + s.user_lookups, 0)
         AS DECIMAL(5,1))                              AS [ДоляСканированийПct],
    s.last_user_seek                                   AS [ПоследнийПоиск],
    s.last_user_scan                                   AS [ПоследнееСканирование]
FROM sys.dm_db_index_usage_stats AS s
WHERE s.database_id = DB_ID()
  AND s.object_id > 100
ORDER BY [ЧтенийВсего] DESC;

-- 2. Таблицы, которые только обновляют и почти не читают — кандидаты на ревизию
SELECT TOP (30)
    OBJECT_NAME(s.object_id)                           AS [Таблица],
    s.user_updates                                     AS [Обновлений],
    s.user_seeks + s.user_scans + s.user_lookups       AS [Чтений]
FROM sys.dm_db_index_usage_stats AS s
WHERE s.database_id = DB_ID()
  AND s.object_id > 100
  AND s.user_updates > 1000
ORDER BY s.user_updates DESC;

-- 3. Индексы, которые «стоят», но обслуживают запись — цена записи (task_188)
SELECT TOP (30)
    OBJECT_NAME(i.object_id)                           AS [Таблица],
    i.name                                             AS [Индекс],
    ISNULL(s.user_updates, 0)                          AS [ОбновленийИндекса],
    ISNULL(s.user_seeks, 0) + ISNULL(s.user_scans, 0)
      + ISNULL(s.user_lookups, 0)                      AS [ИспользованийПриЧтении],
    CAST(ps.used_page_count * 8.0 / 1024 AS DECIMAL(18,2)) AS [РазмерМБ]
FROM sys.indexes AS i
LEFT JOIN sys.dm_db_index_usage_stats AS s
       ON s.object_id = i.object_id AND s.index_id = i.index_id AND s.database_id = DB_ID()
LEFT JOIN sys.dm_db_partition_stats AS ps
       ON ps.object_id = i.object_id AND ps.index_id = i.index_id
WHERE i.object_id > 100
  AND i.is_primary_key = 0
  AND i.is_unique_constraint = 0
  AND i.type > 0
ORDER BY [ОбновленийИндекса] DESC;
