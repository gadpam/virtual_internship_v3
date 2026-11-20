#!/usr/bin/env python3
"""Проверки task_88: дисциплина каталога файлового обмена (зеркало).

Правила: файл готов только с маркером .ok; битый готовый — в errors/;
успешный — в archive/; файл без маркера (ещё пишется) не трогается.
Форматы CSV и XLSX — одним обработчиком.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_file_exchange.py
"""

from __future__ import annotations

import shutil
from pathlib import Path

from openpyxl import Workbook, load_workbook

ROOT = Path("/tmp/rih_exchange_inbox")


def read_price(path: Path) -> list[str]:
    if path.suffix.lower() == ".xlsx":
        wb = load_workbook(path, read_only=True)
        ws = wb.active
        return [str(row[0].value) for row in ws.iter_rows(min_row=2) if row[0].value]
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines[1:]  # заголовок — не строка прайса, как и в XLSX со второй строки


def process(root: Path) -> dict:
    result = {"ok": 0, "errors": 0, "waiting": 0, "rows": 0}
    (root / "archive").mkdir(exist_ok=True)
    (root / "errors").mkdir(exist_ok=True)
    for path in sorted(root.iterdir()):
        if path.suffix.lower() not in (".csv", ".xlsx"):
            continue
        marker = Path(str(path) + ".ok")
        if not marker.exists():
            result["waiting"] += 1
            continue
        try:
            rows = read_price(path)
            if not rows or any(";" not in r and "," not in r for r in rows):
                raise ValueError("строки не похожи на прайс")
            result["rows"] += len(rows)
            shutil.move(str(path), root / "archive" / path.name)
            result["ok"] += 1
        except Exception:
            shutil.move(str(path), root / "errors" / path.name)
            result["errors"] += 1
        marker.unlink()
    return result


def main() -> None:
    if ROOT.exists():
        shutil.rmtree(ROOT)
    (ROOT / "archive").mkdir(parents=True)
    (ROOT / "errors").mkdir()

    (ROOT / "price_good.csv").write_text("sku;price\nSKU-1;10\nSKU-2;20\n", encoding="utf-8")
    Path(str(ROOT / "price_good.csv") + ".ok").touch()

    wb = Workbook()
    ws = wb.active
    ws.append(["sku;price"])
    ws.append(["SKU-3;30"])
    wb.save(ROOT / "price_good.xlsx")
    Path(str(ROOT / "price_good.xlsx") + ".ok").touch()

    (ROOT / "price_broken.csv").write_text("мусор без разделителей\nещё строка\n", encoding="utf-8")
    Path(str(ROOT / "price_broken.csv") + ".ok").touch()

    (ROOT / "price_partial.csv").write_text("sku;price\nSKU-9;90\n", encoding="utf-8")  # без маркера

    result = process(ROOT)
    assert result == {"ok": 2, "errors": 1, "waiting": 1, "rows": 3}, result
    assert (ROOT / "archive" / "price_good.csv").exists()
    assert (ROOT / "archive" / "price_good.xlsx").exists()
    assert (ROOT / "errors" / "price_broken.csv").exists()
    assert (ROOT / "price_partial.csv").exists(), "частичный файл тронут!"
    print(f"[ok] проход каталога: {result}")
    print("[ok] частичный файл без маркера не загружен и остался на месте")


if __name__ == "__main__":
    main()
