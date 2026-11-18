/* =============================================================================
   Назначение : динамика объёма данных и прогноз на 12 месяцев
   Задание    : task_182, вход для task_202 (capacity planning)
   Тип        : только чтение
   Время      : < 30 секунд
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 1. Текущий объём по типам объектов 1С
;WITH current_size AS (
    SELECT
        CASE
            WHEN t.name LIKE '\_InfoR%'   ESCAPE '\' THEN 'Регистры сведений'
            WHEN t.name LIKE '\_AccumR%'  ESCAPE '\' THEN 'Регистры накопления'
            WHEN t.name LIKE '\_Document%' ESCAPE '\' THEN 'Документы'
            WHEN t.name LIKE '\_Reference%' ESCAPE '\' THEN 'Справочники'
            WHEN t.name LIKE '\_ChngR%'   ESCAPE '\' THEN 'Регистры изменений'
            ELSE 'Прочее'
        END                                            AS object_group,
        SUM(a.total_pages) * 8.0 / 1024                AS size_mb,
        SUM(CASE WHEN p.index_id IN (0,1) THEN p.rows ELSE 0 END) AS rows_cnt
    FROM sys.tables AS t
    JOIN sys.indexes AS i ON i.object_id = t.object_id
    JOIN sys.partitions AS p ON p.object_id = i.object_id AND p.index_id = i.index_id
    JOIN sys.allocation_units AS a ON a.container_id = p.partition_id
    WHERE t.is_ms_shipped = 0
    GROUP BY
        CASE
            WHEN t.name LIKE '\_InfoR%'   ESCAPE '\' THEN 'Регистры сведений'
            WHEN t.name LIKE '\_AccumR%'  ESCAPE '\' THEN 'Регистры накопления'
            WHEN t.name LIKE '\_Document%' ESCAPE '\' THEN 'Документы'
            WHEN t.name LIKE '\_Reference%' ESCAPE '\' THEN 'Справочники'
            WHEN t.name LIKE '\_ChngR%'   ESCAPE '\' THEN 'Регистры изменений'
            ELSE 'Прочее'
        END
)
SELECT
    object_group                                       AS [ГруппаОбъектов],
    CAST(size_mb / 1024 AS DECIMAL(18,2))               AS [РазмерГБ],
    rows_cnt                                           AS [Строк],
    CAST(size_mb * 1024.0 / NULLIF(rows_cnt,0) AS DECIMAL(18,1)) AS [БайтНаСтроку]
FROM current_size
ORDER BY [РазмерГБ] DESC;

-- 2. Прирост по месяцам — на примере документов (дата из колонки _DatePeriod/_Period)
--    Для своих таблиц замените имя таблицы и колонки периода.
SELECT
    CAST(d._DatePeriod AS DATE)                        AS [Дата],
    COUNT(*)                                           AS [Документов],
    CAST(COUNT(*) * 1.0 / NULLIF(DATEDIFF(DAY, MIN(d._DatePeriod), MAX(d._DatePeriod)) + 1, 0)
         AS DECIMAL(18,2))                             AS [ВДень]
FROM _Document1234 AS d          -- подставьте реальный номер таблицы документа
GROUP BY CAST(d._DatePeriod AS DATE)
ORDER BY [Дата] DESC;

-- 3. Простой линейный прогноз: средний прирост за 90 дней × 365
DECLARE @avg_per_day DECIMAL(18,2);

SELECT @avg_per_day = AVG(daily_cnt)
FROM (
    SELECT CAST(_DatePeriod AS DATE) AS day, COUNT(*) AS daily_cnt
    FROM _Document1234
    WHERE _DatePeriod >= DATEADD(DAY, -90, GETDATE())
    GROUP BY CAST(_DatePeriod AS DATE)
) AS x;

SELECT
    @avg_per_day                                       AS [ДокументовВДень],
    @avg_per_day * 365                                 AS [ПрогнозНаГод],
    @avg_per_day * 30                                  AS [ПрогнозНаМесяц],
    CAST(@avg_per_day * 365 * 1.5 / 1000000 AS DECIMAL(18,2)) AS [ПрогнозГБпри1_5КБНаСтроку];

/* Вывод для отчёта (заполните):
   - средний прирост: ___ документов в день
   - прогноз на 12 месяцев: ___ строк, ___ ГБ
   - решение: ___ (архивирование / партиционирование / рост диска)
*/
