-- 040: топ товаров с долей дня одним проходом (task_182).
-- Доля — оконная сумма по дню рядом со строкой, без самосоединения.
-- Агрегация до соединения: сначала факты по товарам, потом имена.
WITH per_item AS (
    SELECT day, item_ref, SUM(amount) AS total
    FROM analytics_sales
    GROUP BY day, item_ref
)
SELECT day, item_ref, total,
       ROUND(100.0 * total / SUM(total) OVER (PARTITION BY day), 2) AS share_pct,
       RANK() OVER (PARTITION BY day ORDER BY total DESC) AS place
FROM per_item
ORDER BY day, place;
