#!/usr/bin/env python3
"""Проверки task_17 (строки/GUID/CSV/ISO) — зеркало функций РИХ_ОбщегоНазначения.

Автомат РазобратьCsv повторяет BSL-реализацию посимвольно; эталонный
internship/data/nomenclature_sample.csv не изменяется, только читается.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_strings.py
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def parse_csv(text: str, delimiter: str = ";") -> list[list[str]]:
    rows: list[list[str]] = []
    row: list[str] = []
    field = ""
    in_quotes = False
    i = 0
    while i < len(text):
        ch = text[i]
        if in_quotes:
            if ch == '"':
                if i + 1 < len(text) and text[i + 1] == '"':
                    field += '"'
                    i += 1
                else:
                    in_quotes = False
            else:
                field += ch
        elif ch == '"' and field == "":
            in_quotes = True
        elif ch == delimiter:
            row.append(field)
            field = ""
        elif ch == "\n":
            row.append(field)
            field = ""
            rows.append(row)
            row = []
        elif ch != "\r":
            field += ch
        i += 1
    if field != "" or row:
        row.append(field)
        rows.append(row)
    return rows


GUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def valid_guid(text: str) -> bool:
    return bool(GUID_RE.match(text.strip()))


def to_iso(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def from_iso(text: str) -> datetime:
    raw = text.strip()
    if raw.endswith("Z"):
        return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%S.%fZ" if "." in raw else "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    moment = datetime.strptime(raw[:19], "%Y-%m-%dT%H:%M:%S")
    sign = 1 if raw[19] == "+" else -1
    shift = timedelta(hours=int(raw[20:22]), minutes=int(raw[23:25]))
    return (moment - sign * shift).replace(tzinfo=timezone.utc)


def check(name: str, actual, expected) -> None:
    assert actual == expected, f"{name}: ожидалось {expected!r}, получено {actual!r}"
    print(f"[ok] {name}")


def main() -> None:
    # ISO 8601: туда-обратно, миллисекунды и Z, смещение +03:00
    moment = datetime(2026, 1, 31, 21, 0, tzinfo=timezone.utc)
    check("ISO формат", to_iso(moment), "2026-01-31T21:00:00Z")
    check("ISO разбор Z", from_iso("2026-01-31T21:00:00Z"), moment)
    # платформа 1С хранит секунды: миллисекунды ISO она отбросит; зеркало сохраняет,
    # расхождение в 0.5 с зафиксировано здесь как известная разница типов
    check("ISO разбор миллисекунды", from_iso("2026-01-31T21:00:00.500Z") - moment, timedelta(milliseconds=500))
    check(
        "ISO разбор +03:00",
        from_iso("2026-02-01T00:00:00+03:00"),
        moment,  # то же мгновение другой записью
    )
    # GUID: валидный, мусор, без дефисов
    check("GUID валиден", valid_guid("6f9619ff-8b86-d011-b42d-00c04fc964ff"), True)
    check("GUID мусор", valid_guid("6f9619ff-8b86-d011-b42d-00c04fc964fx"), False)
    check("GUID без дефисов", valid_guid("6f9619ff8b86d011b42d00c04fc964ff"), False)
    check("GUID новый уникален", str(uuid.uuid4()) != str(uuid.uuid4()), True)
    # CSV: кавычки, запятая и перевод строки внутри значения
    text = '1001;"Молоко ""Домик"" 3,2%, 1л";шт\n1002;"Хлеб\nржаной";шт'
    rows = parse_csv(text)
    check("CSV число строк", len(rows), 2)
    check("CSV полей в строке с кавычками", len(rows[0]), 3)
    check("CSV значение с кавычками", rows[0][1], 'Молоко "Домик" 3,2%, 1л')
    check("CSV перевод строки в значении", rows[1][1], "Хлеб\nржаной")
    # Эталонный файл: 21 запись (заголовок + 20), 10 колонок; wc -l даёт 22 из-за пустой последней строки
    sample = Path("data/nomenclature_sample.csv").read_text(encoding="utf-8")
    parsed = parse_csv(sample)
    check("эталон CSV: строк", len(parsed), 21)
    check("эталон CSV: колонок везде 10", {len(r) for r in parsed}, {10})


if __name__ == "__main__":
    main()
