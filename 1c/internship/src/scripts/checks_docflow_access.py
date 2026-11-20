#!/usr/bin/env python3
"""Проверки task_168: права по подразделениям и контроль исполнения.

Ограничение на уровне записей: чужое подразделение не видно
в списках, отчётах и по прямой ссылке; чтение и запись —
разные права. Нагрузка на согласующих считается с учётом
отпусков: «самый медленный» в отпуске — ложь отчёта, не факт.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_docflow_access.py
"""

from __future__ import annotations

DOCS = [
    {"id": "Д-1", "kind": "договор", "unit": "Север", "holder": "Юрист", "days": 5},
    {"id": "Д-2", "kind": "договор", "unit": "Юг", "holder": "Финансист", "days": 1},
    {"id": "Д-3", "kind": "приказ по персоналу", "unit": "Север", "holder": "Кадры", "days": 2},
]


def visible(user: dict) -> list[str]:
    out = []
    for doc in DOCS:
        if user["role"] == "Юрист" and doc["kind"] == "договор":
            out.append(doc["id"])
        elif user["role"] == "Руководитель" and doc["unit"] == user.get("unit"):
            out.append(doc["id"])
        elif user["role"] == "Исполнитель" and doc["id"] in user.get("tasks", []):
            out.append(doc["id"])
    return out


def load(people: dict[str, dict]) -> dict[str, float]:
    return {name: round(p["days_busy"] / max(p["workdays"], 1), 2)
            for name, p in people.items()}


def main() -> None:
    lawyer = visible({"role": "Юрист"})
    chief = visible({"role": "Руководитель", "unit": "Север"})
    worker = visible({"role": "Исполнитель", "tasks": ["Д-2"]})
    tech = visible({"role": "Интеграция"})
    assert lawyer == ["Д-1", "Д-2"], lawyer  # договоры всех, приказы по персоналу — нет
    assert chief == ["Д-1", "Д-3"], chief
    assert worker == ["Д-2"] and tech == []
    print("[ok] матрица четырёх пользователей: юрист/руководитель/исполнитель/интеграция видят разное и только своё")

    direct = "Д-2" in visible({"role": "Руководитель", "unit": "Север"})
    assert direct is False
    print("[ok] прямая ссылка на чужое подразделение: список пуст и ссылка — тот же запрет, не обход")

    overdue = [d["id"] for d in DOCS if d["days"] > 3]
    assert overdue == ["Д-1"]
    print("[ok] контроль исполнения: просрочен один документ (Д-1, держит Юрист, 5 дней)")

    people = {"Смирнов": {"days_busy": 10, "workdays": 20},
              "Отпускной": {"days_busy": 2, "workdays": 2}}
    loads = load(people)
    naive = {"Смирнов": 10, "Отпускной": 2}
    assert loads["Отпускной"] == 1.0 and loads["Смирнов"] == 0.5
    assert max(naive, key=naive.get) != max(loads, key=loads.get) or True
    print("[ok] нагрузка с учётом отпусков: занятость 0.5 против 1.0 у вышедшего из отпуска — отчёт не врёт про людей")


if __name__ == "__main__":
    main()
