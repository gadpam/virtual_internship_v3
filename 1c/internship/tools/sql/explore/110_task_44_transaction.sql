-- task_44: аналог явной транзакции загрузки (PostgreSQL).
-- Ошибка в середине пачки => ROLLBACK: частично загруженных строк нет.
-- Подключение: psql -h /tmp/walk-pg -U rih -d rih -f 110_task_44_transaction.sql
CREATE SCHEMA IF NOT EXISTS lab44;
DROP TABLE IF EXISTS lab44.load_target;
CREATE TABLE lab44.load_target (sku text PRIMARY KEY, name text NOT NULL);

BEGIN;
INSERT INTO lab44.load_target VALUES ('SKU-1','Молоко'), ('SKU-2','Хлеб');
-- протокол загрузки — часть той же транзакции
-- (в 1С это запись журнала/регистра протокола внутри НачатьТранзакцию)
SAVEPOINT before_error;
-- имитация битой строки: дубликат ключа в середине пачки
INSERT INTO lab44.load_target VALUES ('SKU-1','Дубликат');
-- сюда управление не дойдёт: ошибка прервёт транзакцию; в аналоге фиксируем итог:
ROLLBACK;

SELECT 'строк после откаченной загрузки: '||COUNT(*) FROM lab44.load_target;

-- А успешная загрузка фиксируется целиком:
BEGIN;
INSERT INTO lab44.load_target VALUES ('SKU-1','Молоко'), ('SKU-2','Хлеб');
COMMIT;
SELECT 'строк после успешной загрузки: '||COUNT(*) FROM lab44.load_target;
