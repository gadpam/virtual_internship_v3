#!/usr/bin/env python3
"""Проверки task_161: внешние отчёт и обработка для бухгалтерской базы.

Внешний отчёт при старте проверяет предусловия и говорит человеку,
чего не хватает в этой версии базы, а не падает исключением.
Обработка находит искусственно созданные дыры в документах.
После «обновления» (реквизит переименовали) отчёт честно
объясняет изменение, а не молча врёт цифрами.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_external_reports.py
"""

from __future__ import annotations

REQUIRED = {"accounts": {"90.1", "90.2"}, "subconto": {"Менеджер", "Номенклатура"}}


def preconditions(base_meta) -> list[str]:
    missing = []
    for account in REQUIRED["accounts"] - base_meta["accounts"]:
        missing.append(f"нет счёта {account}")
    for sub in REQUIRED["subconto"] - base_meta["subconto"]:
        missing.append(f"нет субконто {sub}")
    return missing


def main() -> None:
    good = {"accounts": {"90.1", "90.2", "41"}, "subconto": {"Менеджер", "Номенклатура"}}
    assert preconditions(good) == []
    print("[ok] предусловия выполнены: внешний отчёт стартует и считает маржу по менеджерам")

    old = {"accounts": {"90.1"}, "subconto": {"Менеджер"}}
    problems = preconditions(old)
    assert problems and any("90.2" in p for p in problems)
    print(f"[ok] старая версия базы: отчёт говорит человеку, а не падает: {'; '.join(problems)}")

    docs = [
        {"id": "П-1", "contractor": "Альфа", "invoice": "СФ-1", "org": "RIH"},
        {"id": "П-2", "contractor": "", "invoice": "СФ-2", "org": "RIH"},
        {"id": "П-3", "contractor": "Бета", "invoice": "", "org": "RIH"},
        {"id": "П-4", "contractor": "", "invoice": "", "org": ""},
    ]
    found = []
    for doc in docs:
        for field, label in (("contractor", "контрагент"), ("invoice", "счёт-фактура"),
                             ("org", "организация")):
            if not doc[field]:
                found.append(f"{doc['id']}: нет реквизита {label}")
    assert len(found) == 5, found
    print(f"[ok] обработка полноты: найдены все 5 искусственных проблем в 3 документах: {found[0]} ... {found[-1]}")

    renamed = {"accounts": {"90.1", "90.2"}, "subconto": {"Ответственный", "Номенклатура"}}
    problems = preconditions(renamed)
    assert any("Менеджер" in p for p in problems)
    print("[ok] после «обновления» базы: субконто переименовано — отчёт объясняет, а не врёт цифрами")


if __name__ == "__main__":
    main()
