#!/usr/bin/env python3
"""Учебная репетиция восстановления из резервной копии (task_193, task_194, task_263).

Скрипт не работает с реальной СУБД: он моделирует последовательность шагов
восстановления и ведёт протокол, чтобы стажёр отработал порядок действий,
проверки и фиксацию RTO. Реальные команды T-SQL приведены в
tools/sql/backup/README.md.

Пример:
    python3 restore_from_backup.py ../../build/backup --target rehearsal --rto-minutes 30
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List

STEPS = [
    ("announce", "Уведомление участников: окно восстановления открыто"),
    ("freeze", "Остановка записи: регламентные задания и интеграции приостановлены"),
    ("verify_backup", "Проверка копии: размер, контрольная сумма, дата"),
    ("restore_full", "Восстановление полной копии (FULL)"),
    ("restore_diff", "Восстановление разностной копии (DIFFERENTIAL), если есть"),
    ("restore_logs", "Накат журнала транзакций (LOG) до точки восстановления"),
    ("consistency_check", "Проверка целостности: DBCC CHECKDB-эквивалент"),
    ("smoke", "Дымовой прогон: вход, проведение документа, отчёт, обмен"),
    ("unfreeze", "Снятие блокировки записи, запуск регламентных заданий"),
    ("report", "Протокол восстановления и фактический RTO"),
]


def rehearse(backup_dir: Path, target: str, rto_minutes: float, dry_run: bool) -> Dict[str, object]:
    started = time.perf_counter()
    log: List[Dict[str, object]] = []
    backup_files = sorted(backup_dir.glob("*.bak")) if backup_dir.exists() else []

    for code, description in STEPS:
        if dry_run:
            log.append({"step": code, "description": description, "status": "planned"})
            continue
        step_started = time.perf_counter()
        status = "ok"
        detail = ""

        if code == "verify_backup":
            if not backup_files:
                status, detail = "failed", f"в {backup_dir} нет файлов .bak"
            else:
                detail = f"найдено копий: {len(backup_files)}; последняя: {backup_files[-1].name}"
        elif code == "smoke" and status == "ok":
            detail = "4 из 4 проверок пройдено"

        log.append({"step": code, "description": description, "status": status, "detail": detail,
                    "seconds": round(time.perf_counter() - step_started, 3)})
        if status == "failed":
            break

    elapsed_minutes = (time.perf_counter() - started) / 60
    report = {
        "target": target,
        "startedAt": datetime.now(timezone.utc).isoformat(),
        "dryRun": dry_run,
        "backupDir": str(backup_dir),
        "backupFiles": [f.name for f in backup_files],
        "steps": log,
        "rtoMinutesPlanned": rto_minutes,
        "rtoMinutesActual": round(elapsed_minutes, 3),
        "rtoMet": elapsed_minutes <= rto_minutes,
        "completed": all(step["status"] != "failed" for step in log),
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Репетиция восстановления из резервной копии")
    parser.add_argument("backup_dir", help="каталог с копиями (internship/build/backup)")
    parser.add_argument("--target", default="rehearsal", help="имя целевого стенда/базы")
    parser.add_argument("--rto-minutes", type=float, default=30.0, help="плановый RTO в минутах")
    parser.add_argument("--dry-run", action="store_true", help="только план шагов")
    parser.add_argument("--output", default=None, help="куда сохранить протокол JSON")
    args = parser.parse_args()

    report = rehearse(Path(args.backup_dir), args.target, args.rto_minutes, args.dry_run)
    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)

    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
        print(f"протокол сохранён: {args.output}", file=sys.stderr)

    return 0 if report["completed"] and report["rtoMet"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
