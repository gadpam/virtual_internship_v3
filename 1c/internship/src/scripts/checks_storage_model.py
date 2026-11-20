#!/usr/bin/env python3
"""Проверки task_181: хранение объектов в СУБД (контур PostgreSQL).

«Физические» таблицы стенда повторяют укладку платформы:
справочник, шапка документа и строки табличной части отдельно,
движения регистра строками. 5 запросов диагностики; остатка
«готовой цифрой» в движениях нет — его считает агрегация, и она
сверяется с запросом уровня виртуальной таблицы.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_storage_model.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS storage CASCADE;
CREATE SCHEMA storage;
CREATE TABLE storage._reference_items (id text PRIMARY KEY, code text, name text);
CREATE TABLE storage._document_receipt (id text PRIMARY KEY, number text, item_ref text);
CREATE TABLE storage._document_receipt_goods (doc_id text, line_no int, item_ref text, qty numeric);
CREATE TABLE storage._accum_stock (period date, doc_id text, kind text, item_ref text, qty numeric);
INSERT INTO storage._reference_items VALUES
 ('ref-1','SKU-0001','Товар А'),('ref-2','SKU-0002','Товар Б');
INSERT INTO storage._document_receipt VALUES ('doc-1','П-001','ref-1');
INSERT INTO storage._document_receipt_goods VALUES
 ('doc-1',1,'ref-1',50),('doc-1',2,'ref-2',10);
INSERT INTO storage._accum_stock VALUES
 ('2026-01-10','doc-1','приход','ref-1',50),('2026-01-15','doc-2','расход','ref-1',30);
""")

    items = psql("SELECT code || '=' || name FROM storage._reference_items ORDER BY code")
    assert "SKU-0001=Товар А" in items
    lines = psql("""
SELECT count(*) FROM storage._document_receipt_goods WHERE doc_id='doc-1'""")
    assert lines == "2", lines
    print("[ok] запросы 1-2: справочник таблицей, строки табличной части — отдельной таблицей со ссылкой на шапку")

    joined = psql("""
SELECT i.name || ':' || g.qty FROM storage._document_receipt_goods g
JOIN storage._reference_items i ON i.id = g.item_ref ORDER BY g.line_no""")
    assert "Товар А:50" in joined and "Товар Б:10" in joined
    total = psql("SELECT round(sum(qty),2) FROM storage._document_receipt_goods")
    assert float(total) == 60.0
    print("[ok] запросы 3-4: соединение документа со справочником по ссылке-ключу, сумма строк 60")

    naive = psql("SELECT round(sum(qty),2) FROM storage._accum_stock WHERE item_ref='ref-1'")
    rest = psql("""
SELECT round(sum(CASE WHEN kind='приход' THEN qty ELSE -qty END),2)
FROM storage._accum_stock WHERE item_ref='ref-1'""")
    assert float(naive) == 80.0 and float(rest) == 20.0, (naive, rest)
    print("[ok] запрос 5 и сравнение: сырые движения суммой дают 80, остаток виртуальной таблицы — 20; готовой цифры в таблице нет")


if __name__ == "__main__":
    main()
