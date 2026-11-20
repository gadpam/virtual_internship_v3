-- 080: дубли по бизнес-ключу целиком (task_182).
-- Ключ — внешний идентификатор + система, а не наименование,
-- которое люди пишут тремя способами. HAVING оставляет только
-- повторения: интерфейс эту грязь не покажет никогда.
SELECT source_system, external_id, COUNT(*) AS copies
FROM analytics_inbox
GROUP BY source_system, external_id
HAVING COUNT(*) > 1
ORDER BY copies DESC;
