#!/usr/bin/env python3
"""Проверки task_170: карта маршрута разбора ошибки интеграции.

Экземпляр стартует из журнала сразу с контекстом сообщения;
критичность ветвит маршрут; задача без результата этап не
закрывает (RIH-PROC-001); один живой процесс на сообщение.
5 экземпляров по веткам доходят до завершения.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_process_route.py
"""

from __future__ import annotations

RUNNING: dict[str, dict] = {}


def stages(criticality: str) -> list[str]:
    if criticality == "критичная":
        return ["Диагностика(30 мин)", "Эскалация дежурному",
                "Исправление", "Проверка", "Закрытие"]
    return ["Диагностика", "Исправление", "Проверка", "Закрытие"]


def start(message_id: str, criticality: str) -> dict:
    if message_id in RUNNING and not RUNNING[message_id]["done"]:
        return RUNNING[message_id]
    proc = {"message": message_id, "stages": stages(criticality),
            "at": 0, "done": False, "results": []}
    RUNNING[message_id] = proc
    return proc


def complete_task(proc: dict, result: str) -> None:
    if not result.strip():
        raise ValueError("RIH-PROC-001: задача без результата не закрывает этап")
    proc["results"].append(result)
    proc["at"] += 1
    if proc["at"] == len(proc["stages"]):
        proc["done"] = True


def main() -> None:
    usual = start("MSG-1", "обычная")
    assert usual["stages"] == ["Диагностика", "Исправление", "Проверка", "Закрытие"]
    crit = start("MSG-2", "критичная")
    assert "Эскалация дежурному" in crit["stages"] and len(crit["stages"]) == 5
    print("[ok] ветвление по критичности: обычная — 4 этапа, критичная — короткий маршрут с эскалацией")

    try:
        complete_task(usual, "  ")
        raise SystemExit("задача без результата закрыла этап")
    except ValueError as error:
        assert "RIH-PROC-001" in str(error)
    print("[ok] задача без результата этап не закрывает: RIH-PROC-001, процесс стоит на месте честно")

    again = start("MSG-1", "обычная")
    assert again is usual
    print("[ok] повторный запуск из журнала по тому же сообщению возвращает живой процесс, не второй разбор")

    for index in range(5):
        proc = start(f"BULK-{index}", "критичная" if index % 2 else "обычная")
        while not proc["done"]:
            complete_task(proc, f"результат этапа {proc['at']}")
        assert proc["done"] and len(proc["results"]) == len(proc["stages"])
    print("[ok] 5 экземпляров по разным веткам дошли до завершения, история результатов сохранена")


if __name__ == "__main__":
    main()
