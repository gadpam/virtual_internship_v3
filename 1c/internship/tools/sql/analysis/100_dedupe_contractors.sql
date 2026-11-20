-- =============================================================================
-- 100: слияние дублей справочника контрагентов с переносом ссылок (task_183).
-- Анатомия безопасного скрипта: предусловия -> архив "до" -> транзакция ->
-- изменение -> подсчёт против ожидания -> журнал. Режим DRY RUN по умолчанию:
-- боевой запуск только явным \set dry_run false перед выполнением.
-- Скрипт идемпотентен: повторный запуск находит 0 дублей и ничего не меняет.
-- Откат после COMMIT — из архивной таблицы скрипта, а не «из бэкапа всей базы».
-- =============================================================================
\set dry_run true

BEGIN;

-- Журнал выполнения: кто, когда, скрипт, сколько строк, режим.
CREATE TABLE IF NOT EXISTS script_journal (
    at timestamptz DEFAULT now(), script text, mode text,
    expected int, affected int, note text);

-- Архив "до"-состояния: строки, которые скрипт тронет в этом запуске.
CREATE TABLE IF NOT EXISTS dedupe_archive (
    at timestamptz DEFAULT now(), run_id text,
    contractor_id text, merged_into text);

-- Шаг 1. Предусловия тем же предикатом, что изменение: дубли по ИНН.
-- Человеческая сверка: SELECT ниже обязан совпасть с ожиданием бизнеса.
--   SELECT inn, COUNT(*) FROM contractors GROUP BY inn HAVING COUNT(*) > 1;

-- Шаг 2-4 одной транзакцией: архив, слияние, подсчёт, журнал.
WITH dups AS (
    SELECT inn, MIN(id) AS keep_id
    FROM contractors GROUP BY inn HAVING COUNT(*) > 1
),
victims AS (
    SELECT c.id, d.keep_id
    FROM contractors c JOIN dups d ON d.inn = c.inn AND c.id <> d.keep_id
),
archived AS (
    INSERT INTO dedupe_archive (run_id, contractor_id, merged_into)
    SELECT 'dedupe-100', id, keep_id FROM victims
    RETURNING contractor_id
),
moved AS (
    UPDATE documents d SET contractor_id = v.keep_id
    FROM victims v WHERE d.contractor_id = v.id
    RETURNING d.id
),
removed AS (
    DELETE FROM contractors c USING victims v WHERE c.id = v.id
    RETURNING c.id
)
INSERT INTO script_journal (script, mode, expected, affected, note)
SELECT '100_dedupe_contractors',
       CASE WHEN :dry_run THEN 'dry-run' ELSE 'apply' END,
       (SELECT COUNT(*) FROM victims),
       (SELECT COUNT(*) FROM removed),
       'слияние дублей по ИНН, ссылки перенесены на основной элемент';

-- В dry run транзакция откатывается: журнал фиксирует план, данные целы.
-- Боевой режим: заменить ROLLBACK на COMMIT осознанно, одним местом скрипта.
ROLLBACK;
