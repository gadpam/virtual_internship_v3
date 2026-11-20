#!/usr/bin/env python3
"""Проверки task_174: процесс RIH и внешний трекер: состояния без дублей.

Процесс разбора создаёт задачу в трекере внешним ключом
(external_ref): повторная синхронизация возвращает ту же задачу,
а не близнеца. Статусы едут по таблице соответствия, незаконный
переход трекер отклоняет 422 — клиент обязан это обработать.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_process_tracker.py
"""

from __future__ import annotations

import json
import os
import urllib.request
import uuid

BASE = "http://localhost:8024"
KEY = os.getenv("MOCK_TRACKER_API_KEY", "mock-tracker-key")
STATUS_MAP = {"Новая": "new", "ВРаботе": "in_progress", "Решена": "resolved",
              "Закрыта": "closed", "ОжидаетПартнёра": "blocked"}


def call(method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(
        BASE + path, data=data, method=method,
        headers={"X-Api-Key": KEY, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read().decode() or "{}")


def main() -> None:
    health_status, health = call("GET", "/health")
    assert health_status == 200 and health["service"] == "mock_tracker_api", health
    print(f"[ok] трекер жив: {health['issues']} задач на стенде")

    ref = f"PROC-{uuid.uuid4().hex[:12]}"
    code, created = call("POST", "/api/v1/issues", {
        "external_ref": ref, "title": "Разбор ошибки обмена MSG-LIVE",
        "description": "процесс RIH_РазборОшибкиИнтеграции",
        "priority": "high", "assignee": "integrator", "due_in_hours": 4})
    assert code == 201 and created["status"] == "new", (code, created)
    issue_id = created["issueId"]

    code, duplicate = call("POST", "/api/v1/issues", {
        "external_ref": ref, "title": "повторная синхронизация",
        "priority": "high", "due_in_hours": 4})
    assert code in (200, 201) and duplicate["issueId"] == issue_id, (code, duplicate)
    print("[ok] идемпотентность: повтор по external_ref вернул ту же задачу, дубля синхронизация не создала")

    code, moved = call("PATCH", f"/api/v1/issues/{issue_id}",
                       {"status": STATUS_MAP["ВРаботе"]})
    assert code == 200 and moved["status"] == "in_progress", (code, moved)
    code, fresh = call("POST", "/api/v1/issues", {
        "external_ref": ref + "-fresh", "title": "проверка матрицы переходов",
        "priority": "low", "due_in_hours": 24})
    fresh_id = fresh["issueId"]
    code, illegal = call("PATCH", f"/api/v1/issues/{fresh_id}",
                         {"status": "resolved"})
    assert code == 422, (code, illegal)
    resolved_code, _ = call("PATCH", f"/api/v1/issues/{issue_id}",
                            {"status": STATUS_MAP["Решена"]})
    assert resolved_code == 200, resolved_code
    print("[ok] статусы по таблице соответствия: ВРаботе -> Решена; прыжок new -> resolved трекер отклонил 422")

    code, comment = call("POST", f"/api/v1/issues/{issue_id}/comments",
                         {"author": "rih-process", "text": "причина: партнёр вернул 503, повтор обмена успешен"})
    assert code == 201, (code, comment)
    code, sla = call("GET", "/api/v1/sla")
    assert code == 200 and "items" in sla
    print("[ok] комментарий разбора и SLA-список трекера отвечают: журнал живёт в трекере, RIH хранит ссылку")


if __name__ == "__main__":
    main()
