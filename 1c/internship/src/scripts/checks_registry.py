#!/usr/bin/env python3
"""Проверки task_120: реестр интеграций и отчёт «под угрозой» (зеркало).

Реестр живёт в documentation/integration_registry.md рядом с кодом:
проверяется, что потоков не меньше 12, обязательные поля заполнены,
статусы из жизненного цикла, а отчёт угроз находит именно те записи,
у которых нет владельца, документации, мониторинга или даты решения.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_registry.py
"""

from __future__ import annotations

from pathlib import Path

REGISTRY = Path("documentation/integration_registry.md")
STATUSES = {"действует", "заморожена", "выведена из эксплуатации"}
CRITICALITY = {"высокая", "средняя", "низкая"}


def parse_registry(text: str) -> list[dict]:
    rows = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("| INT-"):
            continue
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != 9:
            continue
        rows.append({"code": cells[0], "flow": cells[1], "method": cells[2],
                     "owner": cells[3], "criticality": cells[4], "sla": cells[5],
                     "status": cells[6], "docs": cells[7], "monitoring": cells[8]})
    return rows


def base_status(row: dict) -> str:
    return row["status"].split("(")[0].strip()


def at_risk(rows: list[dict]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for row in rows:
        reasons = []
        if base_status(row) != "выведена из эксплуатации":
            if not row["owner"]:
                reasons.append("нет владельца")
            if not row["docs"]:
                reasons.append("нет документации")
            monitoring = row["monitoring"].split("·")[0].strip()
            if not monitoring or monitoring == "не требуется":
                reasons.append("нет мониторинга")
        if base_status(row) == "заморожена" and "без даты" in row["status"]:
            reasons.append("заморожена без даты решения")
        if reasons:
            result[row["code"]] = reasons
    return result


def release_ready(rows: list[dict], code: str) -> bool:
    row = next((item for item in rows if item["code"] == code), None)
    return bool(row and row["owner"] and row["docs"] and base_status(row) == "действует")


def main() -> None:
    text = REGISTRY.read_text(encoding="utf-8")
    rows = parse_registry(text)
    assert len(rows) >= 12, len(rows)
    codes = [row["code"] for row in rows]
    assert len(codes) == len(set(codes)), "коды потоков не уникальны"
    for row in rows:
        assert base_status(row) in STATUSES, row
        assert row["criticality"] in CRITICALITY, row
        assert row["flow"] and row["method"] and row["sla"], row
        assert row["owner"] != "ИТ-отдел", row
    print(f"[ok] реестр заполнен: потоков {len(rows)}, коды уникальны, статусы и критичность из словарей")

    risk = at_risk(rows)
    assert set(risk) == {"INT-09", "INT-12", "INT-14"}, risk
    assert "нет документации" in risk["INT-09"]
    assert "нет мониторинга" in risk["INT-12"]
    print(f"[ok] отчёт «Интеграции под угрозой» нашёл {len(risk)}: "
          + "; ".join(f"{code} — {', '.join(reasons)}" for code, reasons in sorted(risk.items())))

    statuses = {status: sum(base_status(r) == status for r in rows) for status in STATUSES}
    print(f"[ok] жизненный цикл: {statuses}")

    assert release_ready(rows, "INT-01") and not release_ready(rows, "INT-09")
    assert not release_ready(rows, "INT-99")
    assert "нет реестра — нет релиза" in text
    print("[ok] правило «нет реестра — нет релиза»: готовая интеграция проходит, поток без документации и неизвестный код — нет")

    assert "История изменений" in text and "task_114" in text
    print("[ok] история изменений и связь с мониторингом task_114 зафиксированы в реестре")


if __name__ == "__main__":
    main()
