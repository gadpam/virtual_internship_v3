#!/usr/bin/env python3
"""Проверки task_15 (даты/периоды/пояса) — зеркало функций модуля РИХ_Дата.

Кейсы совпадают с проверками, которые в task_52 переедут в каркас 1С:
31 декабря, 29 февраля високосного года, переход через год, пустая дата,
летнее время. Пояса: сеанс Europe/Minsk (UTC+3, без летнего времени),
контрагент Europe/Berlin (летнее время есть).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_dates.py
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

MINSK = ZoneInfo("Europe/Minsk")
BERLIN = ZoneInfo("Europe/Berlin")
EMPTY = datetime(1, 1, 1)


def boundaries(moment: datetime, kind: str) -> tuple[datetime, datetime]:
    if moment == EMPTY:
        return EMPTY, EMPTY
    if kind == "День":
        start = moment.replace(hour=0, minute=0, second=0)
        return start, start + timedelta(days=1) - timedelta(seconds=1)
    if kind == "Неделя":
        start = (moment - timedelta(days=moment.weekday())).replace(
            hour=0, minute=0, second=0
        )
        return start, start + timedelta(days=7) - timedelta(seconds=1)
    if kind == "Месяц":
        start = moment.replace(day=1, hour=0, minute=0, second=0)
        nxt = (start + timedelta(days=32)).replace(day=1)
        return start, nxt - timedelta(seconds=1)
    if kind == "Квартал":
        q_month = 3 * ((moment.month - 1) // 3) + 1
        start = moment.replace(month=q_month, day=1, hour=0, minute=0, second=0)
        nxt = (start + timedelta(days=95)).replace(day=1)
        nxt = nxt.replace(month=3 * ((nxt.month - 1) // 3) + 1)
        return start, nxt - timedelta(seconds=1)
    if kind == "Год":
        start = moment.replace(month=1, day=1, hour=0, minute=0, second=0)
        return start, start.replace(year=start.year + 1) - timedelta(seconds=1)
    raise ValueError(kind)


def check(name: str, actual, expected) -> None:
    assert actual == expected, f"{name}: ожидалось {expected!r}, получено {actual!r}"
    print(f"[ok] {name}")


def main() -> None:
    # 1. 31 декабря: месяц и год заканчиваются 31.12 23:59:59
    d = datetime(2026, 12, 31, 15, 0)
    check("31.12 месяц", boundaries(d, "Месяц"), (datetime(2026, 12, 1), datetime(2026, 12, 31, 23, 59, 59)))
    check("31.12 год", boundaries(d, "Год"), (datetime(2026, 1, 1), datetime(2026, 12, 31, 23, 59, 59)))
    # 2. 29 февраля високосного года: конец месяца — 29.02, не 28.02
    check(
        "29.02 високосный",
        boundaries(datetime(2028, 2, 29, 10, 0), "Месяц"),
        (datetime(2028, 2, 1), datetime(2028, 2, 29, 23, 59, 59)),
    )
    # 3. Переход через год: неделя с 31.12 уходит в следующий год концом
    start, end = boundaries(datetime(2026, 12, 31), "Неделя")
    check("неделя через год: конец", end, datetime(2027, 1, 3, 23, 59, 59))
    # 4. Пустая дата возвращается как есть (не падает, не «сегодня»)
    check("пустая дата", boundaries(EMPTY, "Месяц"), (EMPTY, EMPTY))
    # 5. Квартал: Q4 начинается 01.10
    check(
        "квартал",
        boundaries(datetime(2026, 11, 15), "Квартал"),
        (datetime(2026, 10, 1), datetime(2026, 12, 31, 23, 59, 59)),
    )
    # 6. Пояса: одно мгновение — разные локальные даты у партнёров
    utc_moment = datetime(2026, 1, 31, 21, 0, tzinfo=timezone.utc)
    check("UTC->Минск", utc_moment.astimezone(MINSK).strftime("%Y-%m-%d %H:%M"), "2026-02-01 00:00")
    # 7. Летнее время: Berlin зимой UTC+1, летом UTC+2 — «плюс 2 руками» зимой врёт
    winter = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc).astimezone(BERLIN)
    summer = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc).astimezone(BERLIN)
    check("Berlin смещение зима/лето", (winter.utcoffset(), summer.utcoffset()), (timedelta(hours=1), timedelta(hours=2)))


if __name__ == "__main__":
    main()
