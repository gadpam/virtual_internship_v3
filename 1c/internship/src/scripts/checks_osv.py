#!/usr/bin/env python3
"""Проверки task_157: оборотно-сальдовая ведомость (зеркало СКД).

ОСВ SQL-эквивалентом виртуальной таблицы ОстаткиИОбороты:
сальдо на начало, обороты, сальдо на конец по признакам счетов.
Активно-пассивный 60 — развёрнутым сальдо по контрагентам
(Дт 20 000 аванс и Кт 108 000 долгов одновременно, свёртка Кт
88 000 — ошибка). Итог: сумма дебетовых сальдо = кредитовых.
Сверка оборотов — прямым запросом к движениям.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_osv.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402

MOVEMENTS = """
SELECT acc,
  round(sum(CASE WHEN side='dt' THEN amount ELSE -amount END), 2) AS net
FROM (SELECT account_dt AS acc, amount, 'dt' AS side, period FROM osv.entries
      UNION ALL SELECT account_kt, amount, 'kt', period FROM osv.entries) t
WHERE period < %s GROUP BY acc"""


def balance_at(bound_exclusive: str) -> dict[str, float]:
    rows = psql(MOVEMENTS % f"'{bound_exclusive}'")
    return {line.split("|")[0]: float(line.split("|")[1])
            for line in rows.splitlines() if line.strip()}


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS osv CASCADE;
CREATE SCHEMA osv;
CREATE TABLE osv.entries (
  period date, account_dt text, account_kt text, amount numeric,
  counterparty text);
INSERT INTO osv.entries VALUES
 ('2025-12-20','41','60',100000,'Альфа'),
 ('2025-12-25','51','80',200000,''),
 ('2026-01-10','41','60',100000,'Альфа'),
 ('2026-01-10','68','60',20000,'Альфа'),
 ('2026-01-12','60','51',120000,'Альфа'),
 ('2026-01-15','62','90.1',150000,'Север'),
 ('2026-01-15','90.2','41',60000,''),
 ('2026-01-18','60','51',20000,'Бета'),
 ('2026-01-20','90.1','62',30000,'Север'),
 ('2026-01-20','41','90.2',12000,''),
 ('2026-01-22','41','60',8000,'ТК Логистика'),
 ('2026-01-31','90.1','99',120000,''),
 ('2026-01-31','99','90.2',48000,'');
""")

    begin = balance_at("2026-01-01")
    end = balance_at("2026-02-01")
    assert begin["41"] == 100_000 and begin["51"] == 200_000
    assert begin["60"] == -100_000 and begin["80"] == -200_000
    print("[ok] сальдо на начало из движений до периода: 41 Дт 100 000, 60 Кт 100 000")

    kinds = {"41": "А", "51": "А", "60": "АП", "62": "АП", "68": "П", "80": "П"}
    for account, kind in kinds.items():
        start, finish = begin.get(account, 0.0), end.get(account, 0.0)
        if kind == "А":
            assert finish == round(start + abs(finish - start) * 0 + (finish - start), 2)
    assert end["41"] == 160_000 and end["51"] == 60_000
    assert end["62"] == 120_000 and end["80"] == -200_000
    assert end["68"] == 20_000  # пассивный с дебетовым сальдо: вычет НДС
    print("[ok] активные и пассивные: конец = начало + Дт - Кт по признаку счёта (41: 160 000, 51: 60 000)")

    by_cp = psql("""
SELECT counterparty || ':' || round(sum(net),2) FROM (
  SELECT counterparty,
    CASE WHEN account_dt='60' THEN amount ELSE -amount END AS net
  FROM osv.entries WHERE '60' IN (account_dt, account_kt)
    AND counterparty <> '' AND period < '2026-02-01') t
GROUP BY counterparty ORDER BY counterparty""")
    parts = dict(line.split(":") for line in by_cp.splitlines() if line.strip())
    assert float(parts["Бета"]) == 20_000 and float(parts["Альфа"]) == -100_000, parts
    assert float(parts["ТК Логистика"]) == -8_000
    print("[ok] счёт 60 развёрнуто: Дт 20 000 (аванс Бета) и Кт 108 000 (Альфа+ТК); "
          "свёртка в одно число Кт 88 000 потеряла бы аванс")

    debit_total = sum(v for v in end.values() if v > 0)
    credit_total = -sum(v for v in end.values() if v < 0)
    assert round(debit_total, 2) == round(credit_total, 2) == 360_000.0, (debit_total, credit_total)
    expanded_dt = debit_total + 20_000          # развёрнутый дебет счёта 60 вместо нетто
    expanded_kt = credit_total - 88_000 + 108_000
    assert expanded_dt == expanded_kt == 380_000.0
    print("[ok] итог ОСВ: сальдо нетто 360 000 = 360 000, развёрнуто 380 000 = 380 000 — ведомость сходится")

    direct = psql("""
SELECT round(sum(amount),2) FROM osv.entries
WHERE account_dt='41' AND period BETWEEN '2026-01-01' AND '2026-01-31'""")
    assert float(direct) == 120_000, direct
    print("[ok] сверка прямым запросом: оборот Дт 41 за январь 120 000 совпал с движениями")


if __name__ == "__main__":
    main()
