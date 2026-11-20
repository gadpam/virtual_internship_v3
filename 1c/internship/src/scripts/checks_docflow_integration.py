#!/usr/bin/env python3
"""Проверки task_166: интеграция RIH и документооборота (зеркало).

Договор уезжает на согласование состоянием, а не файлом; событие
возвращает состояние по таблице соответствия. По несогласованному
операции запрещены; аварийный обход — только с обоснованием
и следом в аудите. Повтор события процесс второй раз не двигает.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_docflow_integration.py
"""

from __future__ import annotations

MAPPING = {"НаСогласовании": "НаСогласовании", "Утверждён": "Согласован",
           "Подписан": "Согласован", "Отклонён": "Отклонён"}
accepted_events: set[str] = set()
audit: list[str] = []


class Contract:
    def __init__(self) -> None:
        self.status = "Черновик"
        self.resolution = ""


def apply_event(contract: Contract, event_id: str, state: str, resolution: str = "") -> bool:
    if event_id in accepted_events:
        return False
    accepted_events.add(event_id)
    contract.status = MAPPING.get(state, "Неизвестно")
    contract.resolution = resolution
    return True


def operation_allowed(contract: Contract, emergency: str = "") -> bool:
    if contract.status == "Согласован":
        return True
    if emergency:
        audit.append(f"аварийная операция: {emergency}")
        return True
    return False


def main() -> None:
    contract = Contract()
    assert not operation_allowed(contract)
    apply_event(contract, "EV-1", "НаСогласовании")
    assert contract.status == "НаСогласовании" and not operation_allowed(contract)
    print("[ok] договор на согласовании: RIH видит состояние, операции запрещены")

    apply_event(contract, "EV-2", "Утверждён", "согласовано юристом и финансистом")
    assert operation_allowed(contract)
    again = apply_event(contract, "EV-2", "Отклонён", "повторное событие")
    assert again is False and contract.status == "Согласован"
    print("[ok] утверждён — операции разрешены; повтор события EV-2 состояние второй раз не двигает")

    refused = Contract()
    apply_event(refused, "EV-3", "Отклонён", "п.3: ответственность не ограничена")
    assert not operation_allowed(refused) and "п.3" in refused.resolution
    print("[ok] отклонён: запрет и причина видны в RIH без прыжков между системами")

    assert not operation_allowed(refused)
    assert operation_allowed(refused, "оплата по счёту суда, срок сегодня")
    assert audit and "суда" in audit[0]
    assert not operation_allowed(refused, "")
    print("[ok] аварийный режим: только с обоснованием и записью в аудит; без обоснования — запрет")

    unknown = Contract()
    apply_event(unknown, "EV-4", "Что-то новое из новой версии")
    assert unknown.status == "Неизвестно" and not operation_allowed(unknown)
    print("[ok] неизвестное состояние: запрет по умолчанию — чинить таблицу соответствий, не операции")


if __name__ == "__main__":
    main()
