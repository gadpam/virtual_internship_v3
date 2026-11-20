-- 060: накопительный итог выручки внутри месяца (task_182).
-- Окно ORDER BY день с рамкой по умолчанию: итог растёт строкой
-- за строкой без свёртки фактов в одну цифру месяца.
SELECT day, amount,
       SUM(amount) OVER (PARTITION BY DATE_TRUNC('month', day)
                         ORDER BY day) AS running_total
FROM analytics_sales
ORDER BY day;
