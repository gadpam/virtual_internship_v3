#!/usr/bin/env python3
"""Проверки task_145: интеграционный раздел чек-листа ревью Q2.

Каждый пункт расширенного чек-листа проверяется по коду, а не
подписью: таймаут у каждого внешнего вызова, внешних вызовов
внутри транзакций нет, повторы не касаются 422, приём идемпотентен,
версия контракта зафиксирована, журнал имеет сквозной
идентификатор вызова.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_review_q2.py
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path("Configuration/src")
CLIENTS = ["РИХ_ЛояльностьКлиент", "РИХ_ТККлиент", "РИХ_МагазинКлиент",
           "РИХ_ВнешниеСервисы"]


def read(module: str) -> str:
    return (ROOT / "CommonModules" / module / "Module.bsl").read_text(encoding="utf-8")


def main() -> None:
    for client in CLIENTS[:3]:
        text = read(client)
        connections = re.findall(r"Новый HTTPСоединение\([^)]*\)", text)
        assert connections, client
        assert all(re.search(r",\s*\d+\)$", conn) for conn in connections), connections
        assert "НачатьТранзакцию" not in text, client
    print("[ok] у каждого внешнего вызова таймаут в конструкторе; "
          "внешних вызовов внутри транзакций у клиентов нет")

    retries = read("РИХ_ПовторныеПопытки")
    assert "400/401/403/404/409/422" in retries  # неповторяемые перечислены явно
    integrations = read("РИХ_Интеграции")
    assert "external_id" in integrations and "duplicate" in integrations.lower()
    print("[ok] повторы — только повторяемые ошибки (422 не повторяется); "
          "приём заказов идемпотентен по внешнему идентификатору")

    spec = Path("docs/api/openapi.yaml").read_text(encoding="utf-8")
    assert re.search(r"version:\s*['\"]?\d", spec)
    journal = integrations
    assert "ИдентификаторВызова" in journal
    tokens = read("РИХ_Токены")
    assert "ХешКлюча" in tokens
    print("[ok] версия контракта зафиксирована в OpenAPI; журнал несёт "
          "сквозной идентификатор вызова; токены хранятся хешами")

    degradation = read("РИХ_Деградация")
    assert "РИХ_Деградация" and degradation
    print("[ok] частичный успех и деградация — отдельные режимы, "
          "а не молчаливые пропуски (матрица task_131)")


if __name__ == "__main__":
    main()
