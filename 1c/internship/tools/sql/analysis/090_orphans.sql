-- 090: «осиротевшие» записи (task_182): строки табличной части
-- без документа и движения без регистратора. LEFT JOIN + IS NULL.
-- Перед чисткой проверь легальные источники без регистратора
-- (начальные остатки, ручные операции периода): сирота —
-- диагноз для разбора, а не автоматический DELETE.
SELECT g.doc_id, g.line_no
FROM analytics_doc_goods g
LEFT JOIN analytics_docs d ON d.id = g.doc_id
WHERE d.id IS NULL;

SELECT m.period, m.item_ref, m.qty
FROM analytics_movements m
WHERE m.registrator IS NULL;
