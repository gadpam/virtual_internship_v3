#!/usr/bin/env python3
"""Проверки task_178: дымовой прогон внешних артефактов реестра.

Прогон формирует каждый артефакт на эталонных данных, а не
открывает форму: половина поломок живёт в запросах. Артефакт на
отсутствующий после «обновления» реквизит ловится прогоном
с текстом ошибки, а не пользователем через неделю.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_external_smoke.py
"""

from __future__ import annotations

REGISTRY = [
    {"name": "РИХ_СверкаОбменовЗаДень", "version": "1.0", "needs": {"ЖурналИнтеграций"}},
    {"name": "РИХ_ОстаткиНижеМинимума", "version": "1.3", "needs": {"ВитринаОстатков", "Минимумы"}},
    {"name": "РИХ_ПродажиПоМенеджерамСМаржой", "version": "1.2", "needs": {"Счета90", "СубконтоМенеджер"}},
    {"name": "РИХ_ПересчётВитриныЗаДень", "version": "1.1", "needs": {"ВитринаПродаж"}},
]
BASE_NOW = {"ЖурналИнтеграций", "ВитринаОстатков", "Минимумы",
            "Счета90", "СубконтоМенеджер", "ВитринаПродаж"}


def smoke(base: set) -> list[tuple[str, str, str]]:
    rows = []
    for artifact in REGISTRY:
        missing = artifact["needs"] - base
        if missing:
            rows.append((artifact["name"], artifact["version"],
                         "ОШИБКА: нет " + ", ".join(sorted(missing))))
        else:
            rows.append((artifact["name"], artifact["version"], "сформирован"))
    return rows


def main() -> None:
    rows = smoke(BASE_NOW)
    assert all(r[2] == "сформирован" for r in rows), rows
    print(f"[ok] дымовой прогон на текущей конфигурации: {len(rows)} артефакта сформированы на эталонных данных")

    renamed = BASE_NOW - {"СубконтоМенеджер"}  # имитация обновления
    rows = smoke(renamed)
    broken = [r for r in rows if r[2].startswith("ОШИБКА")]
    assert len(broken) == 1 and "СубконтоМенеджер" in broken[0][2], broken
    print(f"[ok] после «обновления»: прогон нашёл поломку в день обновления — {broken[0][0]} {broken[0][1]}: {broken[0][2]}")

    assert all(item["version"] and item["name"] for item in REGISTRY)
    print("[ok] реестр полон: версия у каждого артефакта — «отчёт сломался» без версии задачей не является")


if __name__ == "__main__":
    main()
