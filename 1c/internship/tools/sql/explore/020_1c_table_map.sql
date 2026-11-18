/* =============================================================================
   Назначение : соответствие таблиц СУБД объектам метаданных 1С
   Задание    : task_181
   Тип        : только чтение
   Время      : < 10 секунд
   Примечание : префиксы таблиц 1С стабильны между версиями платформы:
                _Reference   — справочники
                _Document    — документы
                _InfoR       — регистры сведений
                _AccumR      — регистры накопления
                _AccountingR — регистры бухгалтерии
                _CalcR       — регистры расчёта
                _InfoRSL     — подчинённые таблицы (табличные части)
                _ChngR       — регистр изменений (для планов обмена / CDC)
                _Consts      — константы, _Enums — перечисления
                _Task / _BPr — бизнес-процессы и задачи
   ============================================================================= */

SET NOCOUNT ON;
SET TRANSACTION ISOLATION LEVEL READ UNCOMMITTED;

-- 1. Классификация таблиц по префиксу 1С
SELECT
    CASE
        WHEN t.name LIKE '\_Reference%'     ESCAPE '\' THEN 'Справочник'
        WHEN t.name LIKE '\_Document%'      ESCAPE '\' THEN 'Документ'
        WHEN t.name LIKE '\_InfoRSL%'       ESCAPE '\' THEN 'Табличная часть / подчинённая'
        WHEN t.name LIKE '\_InfoR%'         ESCAPE '\' THEN 'Регистр сведений'
        WHEN t.name LIKE '\_AccumR%'        ESCAPE '\' THEN 'Регистр накопления'
        WHEN t.name LIKE '\_AccountingR%'   ESCAPE '\' THEN 'Регистр бухгалтерии'
        WHEN t.name LIKE '\_CalcR%'         ESCAPE '\' THEN 'Регистр расчёта'
        WHEN t.name LIKE '\_ChngR%'         ESCAPE '\' THEN 'Регистр изменений (обмен/CDC)'
        WHEN t.name LIKE '\_Consts%'        ESCAPE '\' THEN 'Константы'
        WHEN t.name LIKE '\_Enums%'         ESCAPE '\' THEN 'Перечисления'
        WHEN t.name LIKE '\_Task%'          ESCAPE '\' THEN 'Задачи'
        WHEN t.name LIKE '\_BPr%'           ESCAPE '\' THEN 'Бизнес-процессы'
        WHEN t.name LIKE '\_Ftable%'        ESCAPE '\' THEN 'Таблица хранилища файлов'
        WHEN t.name LIKE '\_Sys%'           ESCAPE '\' THEN 'Служебные платформы'
        ELSE 'Прочее'
    END                                                    AS [ТипОбъекта],
    COUNT(*)                                               AS [КоличествоТаблиц]
FROM sys.tables AS t
GROUP BY
    CASE
        WHEN t.name LIKE '\_Reference%'     ESCAPE '\' THEN 'Справочник'
        WHEN t.name LIKE '\_Document%'      ESCAPE '\' THEN 'Документ'
        WHEN t.name LIKE '\_InfoRSL%'       ESCAPE '\' THEN 'Табличная часть / подчинённая'
        WHEN t.name LIKE '\_InfoR%'         ESCAPE '\' THEN 'Регистр сведений'
        WHEN t.name LIKE '\_AccumR%'        ESCAPE '\' THEN 'Регистр накопления'
        WHEN t.name LIKE '\_AccountingR%'   ESCAPE '\' THEN 'Регистр бухгалтерии'
        WHEN t.name LIKE '\_CalcR%'         ESCAPE '\' THEN 'Регистр расчёта'
        WHEN t.name LIKE '\_ChngR%'         ESCAPE '\' THEN 'Регистр изменений (обмен/CDC)'
        WHEN t.name LIKE '\_Consts%'        ESCAPE '\' THEN 'Константы'
        WHEN t.name LIKE '\_Enums%'         ESCAPE '\' THEN 'Перечисления'
        WHEN t.name LIKE '\_Task%'          ESCAPE '\' THEN 'Задачи'
        WHEN t.name LIKE '\_BPr%'           ESCAPE '\' THEN 'Бизнес-процессы'
        WHEN t.name LIKE '\_Ftable%'        ESCAPE '\' THEN 'Таблица хранилища файлов'
        WHEN t.name LIKE '\_Sys%'           ESCAPE '\' THEN 'Служебные платформы'
        ELSE 'Прочее'
    END
ORDER BY [КоличествоТаблиц] DESC;

-- 2. Список таблиц с числом строк (оценка по статистике, без полного сканирования)
SELECT TOP (100)
    SCHEMA_NAME(t.schema_id)                        AS [Схема],
    t.name                                          AS [Таблица],
    SUM(p.rows)                                     AS [СтрокОценка],
    t.create_date                                   AS [Создана],
    t.modify_date                                   AS [Изменена]
FROM sys.tables AS t
JOIN sys.partitions AS p
     ON p.object_id = t.object_id AND p.index_id IN (0, 1)
GROUP BY SCHEMA_NAME(t.schema_id), t.name, t.create_date, t.modify_date
ORDER BY [СтрокОценка] DESC;

-- 3. Таблицы, похожие на объекты RIH: ищем по колонкам с именами 1С-реквизитов
SELECT
    t.name                                          AS [Таблица],
    COUNT(c.column_id)                              AS [Колонок],
    STRING_AGG(CAST(c.name AS VARCHAR(128)), ', ')  AS [КолонкиПервые]
FROM sys.tables AS t
JOIN sys.columns AS c ON c.object_id = t.object_id
WHERE c.name LIKE 'RIH%' OR c.name LIKE '%Fld%'
GROUP BY t.name
ORDER BY t.name;
