-- 070: итоги нескольких уровней одним проходом (task_182).
-- ROLLUP даёт магазин -> все магазины; GROUPING() помечает
-- строки итогов, чтобы «магазин NULL» не читался как магазин.
SELECT shop, item_ref, SUM(amount) AS total,
       GROUPING(shop, item_ref) AS level_mask
FROM analytics_sales
GROUP BY ROLLUP (shop, item_ref)
ORDER BY shop NULLS LAST, total DESC;
