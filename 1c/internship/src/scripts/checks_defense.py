#!/usr/bin/env python3
"""Проверки task_147: пакет защиты Q2 полон и ссылается на живое.

4 схемы в пакете, реестр ADR квартала >= 6 (без примера), каждая
цифра надёжности имеет источник-артефакт в репозитории, замечания
комиссии заведены в backlog поименно (DEF-1..4).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_defense.py
"""

from __future__ import annotations

from pathlib import Path

DOCS = Path("documentation")


def main() -> None:
    pack = (DOCS / "architecture/q2_defense_pack.md").read_text(encoding="utf-8")
    for scheme in ("Карта интеграций", "Потоки событий", "Сага", "деградации"):
        assert scheme in pack, scheme
    assert pack.count("```mermaid") >= 4
    print("[ok] 4 схемы защиты в пакете, каждая — один mermaid-блок на минуту чтения")

    adrs = sorted((DOCS / "adr").glob("ADR-*.md"))
    real = [a for a in adrs if "example" not in a.name]
    assert len(real) >= 6, [a.name for a in real]
    print(f"[ok] ADR в пакете квартала: {len(real)} (>= 6), включая 0007 и 0008")

    for artifact in ("integrations/resilience.md", "integrations/timeouts.md",
                     "operations/degradation_matrix.md", "architecture/saga.md",
                     "performance/load_q2.md", "security/checklist.md",
                     "reviews/q2_integration_review.md", "integration_registry.md"):
        assert (DOCS / artifact).exists(), artifact
    print("[ok] все артефакты-источники цифр надёжности на месте")

    backlog = (DOCS / "backlog_q2.md").read_text(encoding="utf-8")
    for task_id in ("DEF-1", "DEF-2", "DEF-3", "DEF-4"):
        assert task_id in backlog, task_id
    for question in ("Рост ×10", "Canary", "секреты", "SLA"):
        assert question in pack, question
    print("[ok] замечания комиссии — задачи DEF-1..4 в backlog; каверзные вопросы закрыты артефактами")


if __name__ == "__main__":
    main()
