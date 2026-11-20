#!/usr/bin/env python3
"""Проверки task_137: аудит доступа и изменений (зеркало РИХ_Аудит).

Append-only регистр событий: показ ПДн, обезличивание, ротация
секрета, изменение настройки «было → стало», остановка обмена.
Отчёты отвечают за минуты: действия пользователя и доступы
к чувствительным данным. Учебное расследование: «кто отключил
обмен с ТК вчера в 18:00». Архив: сначала выгрузка, потом чистка.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_audit.py
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta

EVENTS: list[dict] = []


def record(user: str, event: str, obj: str, details: str = "",
           was: str = "", became: str = "", at: datetime | None = None) -> None:
    EVENTS.append({"at": at or datetime.now(), "user": user, "event": event,
                   "object": obj, "details": details, "was": was, "became": became})


def mutate(index: int, **changes) -> None:
    raise PermissionError("аудит append-only: правка записей запрещена")


def user_actions(user: str, start: datetime, end: datetime) -> list[dict]:
    return sorted((e for e in EVENTS
                   if e["user"] == user and start <= e["at"] <= end),
                  key=lambda e: e["at"])


def sensitive_access(start: datetime, end: datetime) -> list[dict]:
    return sorted((e for e in EVENTS
                   if e["event"] in ("pdn_view", "pdn_erasure")
                   and start <= e["at"] <= end), key=lambda e: e["at"])


def archive_and_purge(boundary: datetime) -> tuple[str, int]:
    old = [e for e in EVENTS if e["at"] < boundary]
    text = "\n".join(json.dumps({**e, "at": e["at"].isoformat()},
                                ensure_ascii=False) for e in old)
    EVENTS[:] = [e for e in EVENTS if e["at"] >= boundary]  # только после выгрузки
    return text, len(old)


def main() -> None:
    yesterday = datetime.now() - timedelta(days=1)
    stop_time = yesterday.replace(hour=17, minute=58, second=0, microsecond=0)

    record("Петрова А.", "pdn_view", "клиент CL-1042",
           "полный показ телефона по роли ПДн", at=yesterday.replace(hour=11))
    record("Иванов И.", "settings_change", "обмен ТК: расписание",
           "задача обновления UPD-221", was="каждые 15 мин",
           became="остановлен", at=yesterday.replace(hour=17, minute=40))
    record("Иванов И.", "exchange_stop", "обмен с ТК",
           "задача обновления UPD-221", at=stop_time)
    record("Иванов И.", "exchange_start", "обмен с ТК",
           "обновление завершено", at=yesterday.replace(hour=19, minute=5))
    record("Сидорова М.", "secret_rotate", "клиент tk",
           "окно grace 24 часа", at=yesterday.replace(hour=9))
    record("Петрова А.", "pdn_erasure", "клиент CL-2077",
           "по запросу субъекта", at=yesterday.replace(hour=15))

    start, end = yesterday.replace(hour=0), yesterday.replace(hour=23, minute=59)
    stops = [e for e in EVENTS if e["event"] == "exchange_stop"
             and e["object"] == "обмен с ТК" and start <= e["at"] <= end]
    assert len(stops) == 1
    found = stops[0]
    assert found["user"] == "Иванов И." and found["at"] == stop_time
    assert "UPD-221" in found["details"]
    print(f"[ok] расследование: обмен с ТК остановил {found['user']} "
          f"в {found['at']:%H:%M}, основание — {found['details']}")

    ivanov = user_actions("Иванов И.", start, end)
    assert [e["event"] for e in ivanov] == [
        "settings_change", "exchange_stop", "exchange_start"]
    change = ivanov[0]
    assert change["was"] == "каждые 15 мин" and change["became"] == "остановлен"
    print("[ok] отчёт действий пользователя: хронология и версия настройки «было → стало»")

    sensitive = sensitive_access(start, end)
    assert [(e["user"], e["event"]) for e in sensitive] == [
        ("Петрова А.", "pdn_view"), ("Петрова А.", "pdn_erasure")]
    print("[ok] отчёт доступов к чувствительным данным: показы и обезличивания на месте")

    try:
        mutate(0, user="неизвестный")
        raise SystemExit("аудит дал себя отредактировать")
    except PermissionError:
        print("[ok] аудит append-only: правка записи запрещена")

    archive, count = archive_and_purge(yesterday.replace(hour=12))
    assert count == 2 and "secret_rotate" in archive
    assert all(e["at"] >= yesterday.replace(hour=12) for e in EVENTS)
    print(f"[ok] архив: выгружено {count} записей до границы, чистка — после выгрузки")


if __name__ == "__main__":
    main()
