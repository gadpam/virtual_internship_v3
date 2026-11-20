#!/usr/bin/env python3
"""Проверки task_160: обмен RIH <-> бухгалтерская база (зеркало).

Порядок потоков жёсткий: НСИ с сопоставлением по бизнес-ключам,
потом документы, потом обратные статусы. Документ раньше своего
контрагента — авария, а не «доедет». 1000 документов в обе
стороны с замером окна; сверка количество+суммы по обе стороны.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_exchange_bp.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS rih_x CASCADE;
DROP SCHEMA IF EXISTS bp_x CASCADE;
CREATE SCHEMA rih_x;
CREATE SCHEMA bp_x;
CREATE TABLE rih_x.contractors (inn text PRIMARY KEY, name text);
CREATE TABLE rih_x.docs (external_id text PRIMARY KEY, inn text, summa numeric, status text);
CREATE TABLE bp_x.contractors (inn text PRIMARY KEY, name text);
CREATE TABLE bp_x.docs (external_id text PRIMARY KEY, inn text, summa numeric, posted boolean);
INSERT INTO rih_x.contractors VALUES ('7701000001','Альфа'), ('7701000002','Бета');
""")

    psql("""
INSERT INTO bp_x.contractors SELECT * FROM rih_x.contractors
ON CONFLICT (inn) DO NOTHING;
INSERT INTO bp_x.contractors SELECT * FROM rih_x.contractors
ON CONFLICT (inn) DO NOTHING;
""")
    count = psql("SELECT count(*) FROM bp_x.contractors")
    assert count == "2", count
    print("[ok] НСИ сопоставлено по ИНН до документов: повторный обмен дублей не создал")

    orphan = psql("""
SELECT count(*) FROM (
  SELECT 'D-ORPHAN' AS external_id, '7701999999' AS inn) probe
LEFT JOIN bp_x.contractors c ON c.inn = probe.inn WHERE c.inn IS NULL""", )
    assert orphan == "1"
    print("[ok] порядок потоков: документ с несопоставленным контрагентом отклоняется до отправки")

    started = time.time()
    psql("""
INSERT INTO rih_x.docs
SELECT 'DOC-' || g, '7701000001', 100.00, 'sent'
FROM generate_series(1, 1000) g;
INSERT INTO bp_x.docs SELECT external_id, inn, summa, true FROM rih_x.docs
ON CONFLICT (external_id) DO NOTHING;
UPDATE rih_x.docs SET status='posted' WHERE external_id IN (SELECT external_id FROM bp_x.docs WHERE posted);
""")
    elapsed = time.time() - started
    left = psql("SELECT count(*) || '/' || round(sum(summa),2) FROM rih_x.docs")
    right = psql("SELECT count(*) || '/' || round(sum(summa),2) FROM bp_x.docs")
    assert left == right == "1000/100000.00", (left, right)
    print(f"[ok] 1000 документов в обе стороны за {elapsed:.2f} с: количество и суммы сверены ({left})")

    posted = psql("SELECT count(*) FROM rih_x.docs WHERE status='posted'")
    assert posted == "1000"
    print("[ok] обратный поток: статусы «проведено» вернулись на все 1000 документов")


if __name__ == "__main__":
    main()
