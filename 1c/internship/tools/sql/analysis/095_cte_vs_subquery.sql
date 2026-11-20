-- 095: CTE против вложенного подзапроса — сравнение по времени
-- на данных стенда, а не по вкусу (task_182). Смысл один, читается
-- сверху вниз конвейером: каждый шаг именуется по смыслу.
-- Замер на стенде фиксируется в проверках задания; вывод —
-- CTE для людей, план СУБД обычно тот же.
WITH daily AS (
    SELECT day, SUM(amount) AS total FROM analytics_sales GROUP BY day
),
ranked AS (
    SELECT day, total, RANK() OVER (ORDER BY total DESC) AS place FROM daily
)
SELECT * FROM ranked WHERE place <= 3;
