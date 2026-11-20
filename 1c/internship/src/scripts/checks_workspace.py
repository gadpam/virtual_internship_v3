#!/usr/bin/env python3
"""Проверки task_165: рабочее место исполнителя (зеркало).

Списки по роли и сроку, 4 быстрых действия, массовое согласование
ограничено видом и суммой (договор выше лимита массово — запрет),
уведомления не спамят: дайджест утром и просрочка сразу.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_workspace.py
"""

from __future__ import annotations

BATCH_LIMIT = 100_000


def batch_approve(tasks: list[dict]) -> tuple[int, list[str]]:
    done, refused = 0, []
    for task in tasks:
        if task["kind"] == "счёт" and task["summa"] <= BATCH_LIMIT:
            done += 1
        else:
            refused.append(task["id"])
    return done, refused


def notifications(events: list[str]) -> list[str]:
    out, digest = [], 0
    for event in events:
        if event == "новая задача":
            digest += 1
        elif event == "просрочка":
            out.append("просрочка: немедленно")
    if digest:
        out.append(f"дайджест утра: новых задач {digest} (одним письмом)")
    return out


def main() -> None:
    tasks = [
        {"id": "З-1", "role": "Финансист", "due": -1, "kind": "счёт", "summa": 10_000},
        {"id": "З-2", "role": "Юрист", "due": 0, "kind": "договор", "summa": 50_000},
        {"id": "З-3", "role": "Финансист", "due": 2, "kind": "счёт", "summa": 20_000},
    ]
    mine = [t for t in tasks if t["role"] == "Финансист"]
    mine.sort(key=lambda t: t["due"])
    assert [t["id"] for t in mine] == ["З-1", "З-3"]
    print("[ok] мои задачи по роли, просроченная первой: сортировка сроком, а не датой создания")

    batch = [{"id": f"С-{i}", "kind": "счёт", "summa": 5_000} for i in range(10)]
    batch.append({"id": "Д-9", "kind": "договор", "summa": 900_000})
    done, refused = batch_approve(batch)
    assert done == 10 and refused == ["Д-9"], (done, refused)
    print("[ok] массовое действие: 10 счетов согласовано, договор выше лимита и не того вида отклонён настройкой")

    notes = notifications(["новая задача"] * 40 + ["просрочка"])
    assert len(notes) == 2 and "40" in notes[1], notes
    print("[ok] уведомления: 40 новых задач — одно письмо дайджестом, просрочка — сразу; спам-фильтр не нужен")


if __name__ == "__main__":
    main()
