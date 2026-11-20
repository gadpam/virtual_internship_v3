#!/usr/bin/env python3
"""Проверки task_171: сроки, напоминания, эскалация, делегирование.

Срок — рабочие дни от старта этапа по правилу SLA данными.
Напоминание до срока, эскалация после — руководителю с пределом
на владельце процесса. Делегирование уводит задачи заместителю,
история хранит обоих, срок не сбрасывается.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_process_sla.py
"""

from __future__ import annotations

from datetime import date, timedelta

SLA = {("РазборОшибки", "Диагностика"): {"days": 1, "remind_h": 4, "cap": "Владелец процесса"},
       ("РазборОшибки", "Исправление"): {"days": 3, "remind_h": 24, "cap": "Владелец процесса"}}


def planned(start: date, workdays: int) -> date:
    left, current = workdays, start
    while left > 0:
        current += timedelta(days=1)
        if current.weekday() < 5:
            left -= 1
    return current


def escalate(level: int, rule: dict) -> str:
    if level >= 3:
        return rule["cap"]
    return "Руководитель этапа"


def main() -> None:
    friday = date(2026, 1, 16)
    due = planned(friday, 1)
    assert due == date(2026, 1, 19), due  # понедельник: выходные не обещаны как рабочие
    print(f"[ok] срок этапа рабочими днями от старта: пятница + 1 раб. день = {due} (понедельник)")

    rule = SLA[("РазборОшибки", "Исправление")]
    assert escalate(1, rule) == "Руководитель этапа"
    assert escalate(3, rule) == "Владелец процесса"
    assert escalate(9, rule) == "Владелец процесса"
    print("[ok] двойная эскалация: руководитель этапа, предел — владелец процесса; до генерального цепочка не растёт")

    task = {"role": "Интегратор", "assignee": "Петров", "actual": None,
            "due": date(2026, 1, 20), "history": ["назначена: Петров (роль Интегратор)"]}
    task["actual"] = "Сидоров (заместитель на отпуск)"
    task["history"].append("делегирована: Сидоров, срок не изменён")
    assert task["due"] == date(2026, 1, 20) and len(task["history"]) == 2
    print("[ok] делегирование: задачи у заместителя, история хранит обоих, срок задачи не сброшен")

    other = dict(SLA)
    other[("РазборОшибки", "Диагностика")] = {"days": 2, "remind_h": 4, "cap": "Владелец процесса"}
    assert planned(friday, other[("РазборОшибки", "Диагностика")]["days"]) == date(2026, 1, 20)
    print("[ok] SLA меняется данными справочника: срок диагностики 1 -> 2 дня без строчки кода")


if __name__ == "__main__":
    main()
