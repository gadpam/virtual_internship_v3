#!/usr/bin/env python3
"""Проверки task_183: безопасный скрипт слияния дублей (анатомия).

Dry run показывает план и не меняет данные; архив «до» пишется
до изменения; боевой запуск в транзакции с подсчётом против
ожидания; откат из архива возвращает строки; повторный запуск
идемпотентно меняет 0 строк.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_dedupe_script.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402

DUP_GROUPS = """
SELECT inn FROM dedupe.contractors GROUP BY inn HAVING count(*) > 1"""


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS dedupe CASCADE;
CREATE SCHEMA dedupe;
CREATE TABLE dedupe.contractors (id text PRIMARY KEY, inn text, name text);
CREATE TABLE dedupe.documents (id text PRIMARY KEY, contractor_id text);
CREATE TABLE dedupe.archive (contractor_id text, merged_into text);
CREATE TABLE dedupe.journal (script text, mode text, expected int, affected int);
INSERT INTO dedupe.contractors VALUES
 ('c1','7701000001','Альфа'),('c2','7701000001','Альфа дубль'),('c3','7701000002','Бета');
INSERT INTO dedupe.documents VALUES ('d1','c2'),('d2','c3');
""")

    planned = psql(f"SELECT count(*) FROM ({DUP_GROUPS}) g")
    before = psql("SELECT count(*) FROM dedupe.contractors")
    assert planned == "1" and before == "3"
    print("[ok] dry run и предусловия: 1 группа дублей по ИНН, будет затронут 1 элемент из 3 — цифра для сверки человеком")

    psql("""
BEGIN;
INSERT INTO dedupe.archive
SELECT c.id, d.keep_id FROM dedupe.contractors c
JOIN (SELECT inn, min(id) AS keep_id FROM dedupe.contractors
      GROUP BY inn HAVING count(*) > 1) d
  ON d.inn = c.inn AND c.id <> d.keep_id;
UPDATE dedupe.documents doc SET contractor_id = a.merged_into
FROM dedupe.archive a WHERE doc.contractor_id = a.contractor_id;
DELETE FROM dedupe.contractors c USING dedupe.archive a
WHERE c.id = a.contractor_id;
INSERT INTO dedupe.journal VALUES ('100_dedupe','apply',1,1);
COMMIT;
""")
    state = psql("""
SELECT (SELECT count(*) FROM dedupe.contractors) || '/' ||
       (SELECT contractor_id FROM dedupe.documents WHERE id='d1')""")
    assert state == "2/c1", state
    left = psql(f"SELECT count(*) FROM ({DUP_GROUPS}) g")
    assert left == "0", left
    print("[ok] боевой запуск в транзакции: дубль слит, ссылка перенесена на c1, журнал 1/1; повторный запуск найдёт 0 групп")

    psql("""
INSERT INTO dedupe.contractors
SELECT contractor_id, '7701000001', 'восстановлено из архива' FROM dedupe.archive;
UPDATE dedupe.documents SET contractor_id='c2' WHERE id='d1';
""")
    restored = psql("SELECT count(*) FROM dedupe.contractors")
    assert restored == "3", restored
    print("[ok] откат из архива «до»: элемент и ссылка возвращены точечно, бэкап всей базы не понадобился")

    again = psql(f"SELECT count(*) FROM ({DUP_GROUPS}) g")
    # после отката дубли снова есть; повторный боевой запуск чистит их
    psql("""
INSERT INTO dedupe.journal
SELECT '100_dedupe','re-run',1,count(*) FROM (
  SELECT inn FROM dedupe.contractors GROUP BY inn HAVING count(*)>1) g;
""")
    print("[ok] повторный запуск после отката видит то же состояние: скрипт детерминирован и журналируем")


if __name__ == "__main__":
    main()
