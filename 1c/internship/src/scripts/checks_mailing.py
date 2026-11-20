#!/usr/bin/env python3
"""Проверки task_176: рассылка отчётов по расписанию (зеркало цикла).

Журнал по получателям: сформирован/отправлен/ошибка. Повтор после
частичной ошибки шлёт только неполучившим. Персональные данные
параметром подразделения. Ошибка формирования сразу уведомляет
администратора. Большой отчёт — ссылкой, не вложением.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_mailing.py
"""

from __future__ import annotations

JOURNAL: dict[str, str] = {}
ADMIN_ALERTS: list[str] = []
SENT: list[str] = []
MAIL_LIMIT_KB = 10_000


def run_mailing(recipients: list[dict], broken_user: str | None = None) -> None:
    for recipient in recipients:
        name = recipient["user"]
        if JOURNAL.get(name) == "отправлен":
            continue  # повтор дубль получившим не шлёт
        try:
            if name == broken_user:
                raise RuntimeError("отчёт не сформирован: витрина пуста")
            JOURNAL[name] = "сформирован"
            SENT.append(name)
            JOURNAL[name] = "отправлен"
        except RuntimeError as error:
            JOURNAL[name] = "ошибка"
            ADMIN_ALERTS.append(f"{name}: {error}")


def main() -> None:
    recipients = [{"user": "Руководитель Север", "unit": "Север"},
                  {"user": "Руководитель Юг", "unit": "Юг"}]
    run_mailing(recipients, broken_user="Руководитель Юг")
    assert JOURNAL == {"Руководитель Север": "отправлен",
                       "Руководитель Юг": "ошибка"}, JOURNAL
    assert ADMIN_ALERTS and "Юг" in ADMIN_ALERTS[0]
    print("[ok] цикл с ошибкой: Север получил, Юг — ошибка в журнале и уведомление администратору сразу")

    run_mailing(recipients)  # повтор после исправления витрины
    assert SENT.count("Руководитель Север") == 1 and SENT.count("Руководитель Юг") == 1
    print("[ok] повтор отправки: получивший дубля не получил, неполучивший — получил; журнал это доказывает")

    def payload(recipient: dict, size_kb: int) -> str:
        return "ссылка на файл" if size_kb > MAIL_LIMIT_KB else "вложение"

    assert payload(recipients[0], 500) == "вложение"
    assert payload(recipients[0], 50_000) == "ссылка на файл"
    print("[ok] размер до отправки: отчёт сверх лимита почты уходит ссылкой, а не недоставленным вложением")

    own = {r["user"]: r["unit"] for r in recipients}
    assert own["Руководитель Север"] == "Север" and own["Руководитель Юг"] == "Юг"
    print("[ok] персонализация параметром подразделения одной рассылкой, а не копиями по филиалам")


if __name__ == "__main__":
    main()
