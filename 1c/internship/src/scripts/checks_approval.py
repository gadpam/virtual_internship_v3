#!/usr/bin/env python3
"""Проверки task_164: процесс согласования договора, 5 сценариев.

Последовательный маршрут ролей со сроками; отклонение только
с комментарием и возвратом инициатору; просрочка эскалируется
руководителю согласующего; переход дальше запрещён без полноты
решений всех ролей круга.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_approval.py
"""

from __future__ import annotations

ROLES = ["Юрист", "Финансист", "Руководитель"]
SLA_DAYS = {"Юрист": 2, "Финансист": 2, "Руководитель": 1}
CHIEFS = {"Юрист": "Главный юрист", "Финансист": "Финдиректор",
          "Руководитель": "Директор"}


class Process:
    def __init__(self) -> None:
        self.stage = 0
        self.decisions: dict[str, str] = {}
        self.state = "ВРаботе"

    def decide(self, role: str, verdict: str, comment: str = "") -> str:
        if self.state != "ВРаботе" or ROLES[self.stage] != role:
            return "не ваш этап"
        if verdict == "против" and not comment.strip():
            return "отклонение требует комментария"
        self.decisions[role] = verdict
        if verdict == "против":
            self.state = "НаДоработке"
            return "возврат инициатору"
        self.stage += 1
        if self.stage == len(ROLES):
            self.state = "Согласован"
        return "принято"

    def escalate(self, role: str, overdue_days: int) -> str | None:
        if overdue_days > SLA_DAYS[role]:
            return f"эскалация: {CHIEFS[role]} (просрочка этапа {role})"
        return None


def main() -> None:
    done = Process()
    for role in ROLES:
        assert done.decide(role, "за") == "принято"
    assert done.state == "Согласован"
    print("[ok] сценарий «согласован»: три роли последовательно, контроль полноты пропустил к подписанию")

    partial = Process()
    assert partial.decide("Финансист", "за") == "не ваш этап"
    print("[ok] контроль полноты: чужой этап и пропуск этапа запрещены — полнота держит процесс, не человек")

    no_comment = Process()
    assert no_comment.decide("Юрист", "против") == "отклонение требует комментария"
    declined = Process()
    assert declined.decide("Юрист", "против", "п.3 — ответственность не ограничена") == "возврат инициатору"
    assert declined.state == "НаДоработке"
    print("[ok] сценарии «отклонён/доработка»: без комментария нельзя; с причиной — возврат инициатору")

    mail = Process().escalate("Финансист", 3)
    assert mail and "Финдиректор" in mail
    assert Process().escalate("Финансист", 1) is None
    print(f"[ok] сценарий «просрочен»: срок этапа 2 дн, на 3-й — {mail}")

    withdrawn = Process()
    withdrawn.state = "Отозван"
    assert withdrawn.decide("Юрист", "за") == "не ваш этап"
    print("[ok] сценарий «отозван»: отозванный процесс решений не принимает")


if __name__ == "__main__":
    main()
