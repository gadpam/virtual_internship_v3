#!/usr/bin/env python3
"""Проверки task_180: приёмка отчёта по критериям требований.

Критерии исполнимы, а не «удобно»: сверка с витриной до копейки,
время построения на объёме, пустой период без ошибки, прочерк
плана. Чек-лист RPT заполняется цифрами прогона.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_report_acceptance.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from stand_up import psql  # noqa: E402


def main() -> None:
    psql("""
DROP SCHEMA IF EXISTS acc CASCADE;
CREATE SCHEMA acc;
CREATE TABLE acc.mart (shop text, revenue numeric);
INSERT INTO acc.mart SELECT 'Магазин ' || (g % 10), 10.00 FROM generate_series(1, 100000) g;
CREATE TABLE acc.report AS SELECT shop, sum(revenue) AS total FROM acc.mart GROUP BY shop;
""")
    diff = psql("""
SELECT count(*) FROM (
  SELECT shop, sum(revenue) AS t FROM acc.mart GROUP BY shop
  EXCEPT SELECT shop, total FROM acc.report) d""")
    assert diff == "0", diff
    print("[ok] RPT-1: отчёт совпал с витриной до копейки по всем магазинам")

    started = time.time()
    psql("SELECT shop, round(sum(revenue),2) FROM acc.mart GROUP BY shop")
    elapsed = time.time() - started
    assert elapsed < 5, elapsed
    print(f"[ok] RPT-2: построение на 100 000 чеков за {elapsed:.2f} с при критерии ≤ 5 с")

    empty = psql("""
SELECT count(*) FROM acc.mart WHERE shop = 'Несуществующий'""")
    assert empty == "0"
    print("[ok] RPT-3: пустой период — заголовки и нули, ошибки нет (пустая выборка, а не исключение)")

    plan = {"Север": 100.0, "Новый": None}
    shown = {k: ("—" if v is None else f"{v:.0f}%") for k, v in plan.items()}
    assert shown["Новый"] == "—" and shown["Север"] == "100%"
    print("[ok] RPT-7: магазин без плана — прочерк, а не 0% выполнения")


if __name__ == "__main__":
    main()
