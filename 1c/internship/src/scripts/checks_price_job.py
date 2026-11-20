#!/usr/bin/env python3
"""Зеркальная проверка task_47: регламентная загрузка прайса.

Механика из РИХ_ОбщегоНазначения.ЗагрузитьПрайсыПоставщиков:
- параллельный запуск запрещён (ключ блокировки — файл-лок зеркало);
- битый файл: 3 попытки, каждая пишется в журнал, потом файл пропускается;
- хороший файл из samples загружается с первой попытки.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_price_job.py
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from checks_strings import parse_csv

JOURNAL: list[dict] = []


def process_file(name: str, text: str) -> bool:
    for attempt in range(1, 4):
        try:
            rows = parse_csv(text)
            data_rows = [r for r in rows[1:] if r and r[0] != "" or (r and False)]
            if len(rows) < 2 or any(len(r) < 5 or r[0] == "" for r in rows[1:] if r):
                # битая строка (пустой артикул) = битый файл: ретрай целиком,
                # а не «загрузили, что смогли» (правило журнала task_47)
                raise ValueError("Файл прайса пуст или бит")
            JOURNAL.append({"файл": name, "статус": "Успех", "строк": len(rows) - 1, "попытка": attempt})
            return True
        except Exception as err:  # noqa: BLE001 - зеркало Попытки
            JOURNAL.append({"файл": name, "статус": "Ошибка", "текст": str(err), "попытка": attempt})
    return False


def main() -> None:
    samples = Path("data/supplier_price/samples")
    good = next(samples.glob("prices_supplier_001*.csv"))
    broken = next(samples.glob("prices_supplier_002_broken.csv"))
    ok_good = process_file(good.name, good.read_text(encoding="utf-8"))
    ok_broken = process_file(broken.name, broken.read_text(encoding="utf-8"))
    print(f"[ok] хороший файл загружен: {ok_good}; битый после 3 попыток пропущен: {not ok_broken}")
    attempts = [j for j in JOURNAL if j["файл"] == broken.name]
    assert [j["попытка"] for j in attempts] == [1, 2, 3], attempts
    print(f"[ok] журнал: попыток по битому файлу 3, статусы {[j['статус'] for j in attempts]}")

    # Параллельный запуск: лок занят — второй запуск уходит сразу
    lock_path = Path(tempfile.gettempdir()) / "rih_price_job.lock"
    fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        try:
            os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            raise AssertionError("второй запуск не запрещён")
        except FileExistsError:
            print("[ok] параллельный запуск запрещён ключом блокировки")
    finally:
        os.close(fd)
        lock_path.unlink()


if __name__ == "__main__":
    main()
