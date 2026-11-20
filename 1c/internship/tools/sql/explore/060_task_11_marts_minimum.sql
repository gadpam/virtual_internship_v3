-- =============================================================================
-- task_11 (Q1): SQL-минимум на витринах стенда RIH (PostgreSQL, база rih)
-- Запуск: psql -d rih -f 060_task_11_marts_minimum.sql
-- Правило: только чтение. Запись мимо платформы в таблицы 1С запрещена
-- (ломает ссылки, итоги и планы обмена); на стенде работаем со схемой marts.
-- =============================================================================

-- 1) SELECT + WHERE + ORDER BY + LIMIT: топ магазинов по выручке за период
SELECT s.store_code, SUM(f.revenue) AS revenue
FROM marts.fact_sales f
JOIN marts.dim_store s ON s.store_key = f.store_key
WHERE f.date_key >= DATE '2026-11-01'
GROUP BY s.store_code
ORDER BY revenue DESC
LIMIT 5;

-- 2) JOIN + GROUP BY: строки и сумма в разрезе магазинов (весь период)
SELECT s.store_code, COUNT(*) AS rows_cnt, SUM(f.revenue) AS revenue
FROM marts.fact_sales f
JOIN marts.dim_store s ON s.store_key = f.store_key
GROUP BY s.store_code
ORDER BY revenue DESC;

-- 3) Сверка одной цифры двумя независимыми способами:
--    итог по факту против готового представления v_sales_daily.
--    На прогоне 2026-11-17: 746336.03 = 746336.03 (сошлось).
SELECT (SELECT SUM(revenue) FROM marts.fact_sales)  AS fact_sum,
       (SELECT SUM(revenue) FROM marts.v_sales_daily) AS view_sum;

-- 4) «Сироты»: строки факта без измерения. На прогоне: 0
--    (плюс внешние ключи схемы не дали бы им появиться).
SELECT COUNT(*) AS orphans
FROM marts.fact_sales f
LEFT JOIN marts.dim_store s ON s.store_key = f.store_key
WHERE s.store_key IS NULL;

-- 5) Подозрительные места, только на чтение:
--    отрицательные/нулевые значения запрещены CHECK-ами схемы (0 строк на прогоне),
--    а повторяющиеся (магазин, товар, день) — НЕ дубли: зерно факта — строка
--    документа, уникальность держит (doc_ref, product_key).
SELECT COUNT(*) FILTER (WHERE revenue < 0) AS negative_rev,
       COUNT(*) FILTER (WHERE quantity <= 0) AS bad_qty
FROM marts.fact_sales;
