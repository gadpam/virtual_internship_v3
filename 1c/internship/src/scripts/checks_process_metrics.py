#!/usr/bin/env python3
"""Проверки task_173: аналитика процессов — ожидание против работы.

Метрики пишутся по завершении задач в витрину; медиана и p95
вместо среднего. Узкое место находится цифрой: этап Исправление
ждёт 2,8 дня при работе 0,3 часа, возвраты 30%.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_process_metrics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS pm CASCADE;
CREATE SCHEMA pm;
CREATE TABLE pm.stage_facts (
  process text, stage text, role text, wait_h numeric, work_h numeric,
  returned int, overdue boolean);
INSERT INTO pm.stage_facts SELECT 'РазборОшибки','Диагностика','Дежурный',
  2, 0.5, 0, false FROM generate_series(1, 10);
INSERT INTO pm.stage_facts SELECT 'РазборОшибки','Исправление','Интегратор',
  67, 0.3, CASE WHEN g <= 3 THEN 1 ELSE 0 END, g <= 2
FROM generate_series(1, 10) g;
INSERT INTO pm.stage_facts SELECT 'РазборОшибки','Проверка','Дежурный',
  4, 0.4, 0, false FROM generate_series(1, 10);
""")

    median_wait = psql("""
SELECT round(percentile_cont(0.5) WITHIN GROUP (ORDER BY wait_h)::numeric, 1)
FROM pm.stage_facts WHERE stage='Исправление'""")
    median_work = psql("""
SELECT round(percentile_cont(0.5) WITHIN GROUP (ORDER BY work_h)::numeric, 1)
FROM pm.stage_facts WHERE stage='Исправление'""")
    assert float(median_wait) == 67.0 and float(median_work) == 0.3, (median_wait, median_work)
    print(f"[ok] этап Исправление: медиана ожидания {median_wait} ч (2,8 дн) при работе {median_work} ч — узкое место в ожидании, не в людях")

    returns = psql("""
SELECT round(100.0 * sum(returned) / count(*), 0) FROM pm.stage_facts
WHERE stage='Исправление'""")
    assert float(returns) == 30.0, returns
    print(f"[ok] возвраты этапа: {returns}% — чек-лист входа (контекст сообщения) в предложении по маршруту")

    worst = psql("""
SELECT stage FROM pm.stage_facts GROUP BY stage
ORDER BY percentile_cont(0.95) WITHIN GROUP (ORDER BY wait_h) DESC LIMIT 1""")
    assert worst == "Исправление", worst
    print("[ok] p95 ожидания: худший этап — Исправление; предложение: второй исполнитель роли и чек-лист входа")


if __name__ == "__main__":
    main()
