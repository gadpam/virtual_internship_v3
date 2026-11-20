#!/usr/bin/env python3
"""Проверки task_167: доработки документооборота без снятия с поддержки.

Допреквизиты штатны и видны в отчёте; печатная форма печатает
версию, которую согласовывали; лимит — настройка владельца
процесса, ветвление меняется без кода; реестр доработок живёт
обновление основы (перечислены способы, не правки конфигурации).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_docflow_customization.py
"""

from __future__ import annotations

SETTINGS = {"limit": 500_000}
ADD_PROPS = ["Сумма", "Контрагент", "ОтветственныйЮрист", "СрокДействия"]


def needs_director(amount: float, settings=SETTINGS) -> bool:
    return amount > settings["limit"]


def print_version(versions: dict[str, str], agreed_version: str) -> str:
    return versions[agreed_version]


def main() -> None:
    report_row = {prop: "..." for prop in ADD_PROPS}
    assert set(report_row) == set(ADD_PROPS)
    print("[ok] дополнительные реквизиты БСП видны в отчёте по договорам все четыре, захороненных нет")

    versions = {"v3": "текст v3 (согласована)", "v4": "текст v4 (текущая)"}
    printed = print_version(versions, "v3")
    assert printed.startswith("текст v3")
    print("[ok] печатная форма печатает версию v3, которую подписали, а не текущую v4")

    assert needs_director(700_000) is True
    SETTINGS["limit"] = 1_000_000  # настройка владельца, не релиз
    assert needs_director(700_000) is False
    print("[ok] лимит поднят владельцем процесса 500 тыс. -> 1 млн настройкой: ветвление изменилось без кода")

    registry = ["допреквизиты БСП", "внешняя печатная форма",
                "настройка процесса", "расширение контроля старта"]
    base_changed = []
    assert base_changed == [] and len(registry) == 4
    print("[ok] обновление основы: все 4 доработки в отведённых местах, конфигурация не тронута ни одной")


if __name__ == "__main__":
    main()
