#!/usr/bin/env python3
"""Проверки task_146: демо интеграций с управляемым сбоем (репетиция).

Сценарий по минутам из documentation/demo/q2_demo_scenario.md,
прогоняется вживую против моков: норма (заказ → баллы), управляемый
сбой лояльности (очередь растёт, breaker открывается, операции не
теряются), восстановление (очередь доезжает ровно по одному разу,
цифры сходятся), журнал отвечает «где мой заказ?».

Запуск: src/scripts/.venv/bin/python src/scripts/checks_demo.py
"""

from __future__ import annotations

import sys
import time
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from checks_integration import LOYALTY, call  # noqa: E402

KEY = {"X-Api-Key": "mock-loyalty-key"}
BREAKER_THRESHOLD = 5


def main() -> None:
    run = uuid.uuid4().hex[:8]
    card = f"DEMO-{run}"
    queue: list[dict] = []       # очередь отложенных начислений (task_110/131)
    journal: list[str] = []      # журнал демо: ответ на «где мой заказ?»
    failures = 0
    breaker_open = False

    def accrue(operation: str, points: int, fault: bool) -> str:
        nonlocal failures, breaker_open
        if breaker_open:
            journal.append(f"{operation}: breaker открыт, вызов не ушёл партнёру")
            return "queued"
        url = LOYALTY + "/api/v1/accrue" + ("?fault=error500" if fault else "")
        code, _ = call("POST", url,
                       {"operation_id": operation, "card": card, "points": points},
                       KEY)
        if code == 200:
            failures = 0
            journal.append(f"{operation}: начислено {points} баллов")
            return "done"
        failures += 1
        if failures >= BREAKER_THRESHOLD:
            breaker_open = True
            journal.append(f"{operation}: {failures}-я неудача подряд — "
                           "breaker ОТКРЫТ, партнёр отключён от попыток")
        else:
            journal.append(f"{operation}: партнёр 500 (неудача {failures}), "
                           "операция встала в очередь")
        return "queued"

    started = time.time()
    print("=== Акт 1. Норма: заказ оплачен, баллы начисляются ===")
    assert accrue(f"DEMO-{run}-1", 150, fault=False) == "done"
    _, balance = call("GET", f"{LOYALTY}/api/v1/cards/{card}/balance", headers=KEY)
    assert balance["balance"] == 250.0, balance  # 100 стартовых + 150
    print(f"[ok] баланс карты {balance['balance']}: баллы на месте")

    print("=== Акт 2. Управляемый сбой: лояльность легла на глазах ===")
    for i in range(2, 9):
        operation = f"DEMO-{run}-{i}"
        if accrue(operation, 10, fault=True) == "queued":
            queue.append({"operation_id": operation, "points": 10})
    assert breaker_open and len(queue) == 7, (breaker_open, len(queue))
    _, during = call("GET", f"{LOYALTY}/api/v1/cards/{card}/balance", headers=KEY)
    assert during["balance"] == 250.0
    print(f"[ok] очередь выросла до {len(queue)} операций, breaker открыт, "
          f"баланс честно прежний {during['balance']} — продажа не встала")

    print("=== Акт 3. Восстановление: очередь доезжает без дублей ===")
    breaker_open = False
    failures = 0
    for item in queue:
        code, result = call("POST", LOYALTY + "/api/v1/accrue",
                            {"operation_id": item["operation_id"],
                             "card": card, "points": item["points"]}, KEY)
        assert code == 200 and result.get("duplicate") is not True, result
    _, final = call("GET", f"{LOYALTY}/api/v1/cards/{card}/balance", headers=KEY)
    assert final["balance"] == 250.0 + 70, final
    print(f"[ok] все {len(queue)} операций доехали ровно по одному разу: "
          f"баланс {final['balance']} сходится до балла")

    print("=== Акт 4. «Где мой заказ?» — ответ из журнала ===")
    for line in journal:
        print("   ", line)
    assert any("breaker ОТКРЫТ" in line for line in journal)
    print(f"\n[ok] демо по сценарию за {time.time() - started:.1f} с: "
          "сбой управляемый, данные не потеряны, цифры сошлись")


if __name__ == "__main__":
    main()
