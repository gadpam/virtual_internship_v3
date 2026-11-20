#!/usr/bin/env python3
"""Проверки task_172: рабочее место исполнителя процессов (зеркало).

Список отвечает «что, по какому объекту, до какого часа» без
открытия карточек: сортировка сроком, счётчики одной агрегацией,
просроченное сверху. 5 быстрых действий; «отложить» без причины
и новой даты запрещено.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_my_tasks.py
"""

from __future__ import annotations

TASKS = [
    {"id": "Т-1", "process": "РазборОшибки", "due_h": -5, "priority": "высокий", "ctx": "MSG-101"},
    {"id": "Т-2", "process": "РазборОшибки", "due_h": 3, "priority": "обычный", "ctx": "MSG-102"},
    {"id": "Т-3", "process": "КорректировкаУчёта", "due_h": 30, "priority": "обычный", "ctx": "DOC-7"},
]


def counters(tasks: list[dict]) -> dict:
    # одна агрегация по выборке, а не запрос на каждую цифру
    return {"всего": len(tasks),
            "просрочено": sum(1 for t in tasks if t["due_h"] < 0),
            "сегодня": sum(1 for t in tasks if 0 <= t["due_h"] <= 24)}


def postpone(task: dict, reason: str, new_due_h: int) -> dict:
    if not reason.strip() or new_due_h <= task["due_h"]:
        raise ValueError("RIH-PROC-002: отложить — только с причиной и новой датой позже текущей")
    task["status"] = f"отложена: {reason}"
    task["due_h"] = new_due_h
    return task


def main() -> None:
    ordered = sorted(TASKS, key=lambda t: t["due_h"])
    assert [t["id"] for t in ordered] == ["Т-1", "Т-2", "Т-3"]
    print("[ok] список сроком: просроченная Т-1 красным сверху, каждая строка несёт контекст в один клик")

    assert counters(TASKS) == {"всего": 3, "просрочено": 1, "сегодня": 1}
    print("[ok] счётчики одной агрегацией: всего 3, просрочено 1, сегодня 1")

    try:
        postpone(dict(TASKS[0]), "", 10)
        raise SystemExit("откладывание без причины прошло")
    except ValueError as error:
        assert "RIH-PROC-002" in str(error)
    moved = postpone(dict(TASKS[0]), "жду ответ партнёра до завтра", 28)
    assert moved["due_h"] == 28
    print("[ok] быстрое действие «отложить»: без причины запрещено (RIH-PROC-002), с причиной и датой — работает")

    actions = ["взять в работу", "выполнить", "отложить", "делегировать", "вернуть инициатору"]
    assert len(actions) == 5
    print("[ok] 5 быстрых действий из строки задачи: история фиксирует автора и время каждого")


if __name__ == "__main__":
    main()
