#!/usr/bin/env python3
"""Зеркальные проверки task_50: единый JSON-формат событий и маскирование.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_logging.py
"""

from __future__ import annotations

import json

SECRET_HINTS = ("password", "token", "парол", "телефон", "паспорт")


def is_secret(key: str) -> bool:
    low = key.lower()
    return any(hint in low for hint in SECRET_HINTS)


def make_json(event: str, data: dict) -> str:
    payload = {"event": event}
    for key, value in data.items():
        payload[key] = "***" if is_secret(key) else str(value)
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":"))


def main() -> None:
    line = make_json("Проведение.Поступление", {"doc": "ПоступлениеТоваров-17", "movements": 4})
    parsed = json.loads(line)
    assert parsed["event"] == "Проведение.Поступление" and parsed["movements"] == "4"
    print(f"[ok] событие JSON читается машиной: {line}")

    masked = json.loads(make_json("Обмен.Загрузка", {"пользователь": "ivanov", "телефон": "+375291112233", "apiToken": "s3cr3t"}))
    assert masked["телефон"] == "***" and masked["apiToken"] == "***" and masked["пользователь"] == "ivanov"
    print("[ok] ПДн и секреты маскируются кодом, а не надеждой")

    journal = [
        {"event": "Загрузка.Прайс", "level": "Ошибка", "date": "2026-11-17"},
        {"event": "Загрузка.Прайс", "level": "Информация", "date": "2026-11-17"},
        {"event": "Загрузка.План", "level": "Ошибка", "date": "2026-11-16"},
    ]
    errors = [j for j in journal if j["level"] == "Ошибка" and j["date"] == "2026-11-17"]
    assert len(errors) == 1
    print("[ok] отбор ошибок загрузки за период работает по журналу")


if __name__ == "__main__":
    main()
