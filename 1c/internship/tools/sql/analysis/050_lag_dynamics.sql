-- 050: динамика по месяцам против прошлого месяца (task_182).
-- LAG берёт предыдущую строку окна; первый месяц динамики честно
-- даёт NULL, а не «рост с нуля» делением на пустое место.
WITH monthly AS (
    SELECT DATE_TRUNC('month', day) AS month, SUM(amount) AS total
    FROM analytics_sales
    GROUP BY DATE_TRUNC('month', day)
)
SELECT month, total,
       LAG(total) OVER (ORDER BY month) AS prev_month,
       ROUND(100.0 * (total - LAG(total) OVER (ORDER BY month))
             / NULLIF(LAG(total) OVER (ORDER BY month), 0), 2) AS growth_pct
FROM monthly
ORDER BY month;
