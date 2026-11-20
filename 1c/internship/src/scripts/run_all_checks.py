#!/usr/bin/env python3
"""Единый запуск всех зеркальных проверок Q1 (аналог ВыполнитьТесты каркаса).

В ИБ ту же роль играет обработка РИХ_ЮнитТесты (task_52); здесь, без
платформы, одним запуском гоняются все checks_*.py и печатается итог.

Запуск: src/scripts/.venv/bin/python src/scripts/run_all_checks.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

CHECKS = [
    "checks_collections.py",
    "checks_dates.py",
    "checks_money.py",
    "checks_strings.py",
    "checks_posting.py",
    "checks_validation.py",
    "checks_stock_control.py",
    "checks_logging.py",
    "checks_errors.py",
    "checks_price_job.py",
    "checks_locks.py",
    "checks_report_xlsx.py",
    "checks_plan_fact.py",
]


def main() -> None:
    here = Path(__file__).parent
    failed = []
    for name in CHECKS:
        proc = subprocess.run(
            [sys.executable, str(here / name)],
            capture_output=True, text=True, cwd=here.parent.parent,
        )
        ok_count = proc.stdout.count("[ok]")
        status = "ok" if proc.returncode == 0 else "FAIL"
        print(f"{status:4} {name}: проверок [ok] = {ok_count}")
        if proc.returncode != 0:
            failed.append(name)
            print(proc.stdout[-800:])
            print(proc.stderr[-800:])
    print(f"ИТОГ: файлов {len(CHECKS)}, упало {len(failed)}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
