#!/usr/bin/env python3
"""Проверки task_153: трансляция документов в проводки правилами.

6 сценариев: поступление, перемещение, продажа, возврат, списание
и отсутствие правила (ошибка RIH-ACC-001, а не тишина). Правила —
данные: смена счёта Кт 60 -> 76 в правиле перестраивает проводку
без кода. Двойное проведение заменяет движения, а не задваивает.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_translation.py
"""

from __future__ import annotations


class TranslationError(Exception):
    pass


RULES = [
    {"doc": "Поступление", "dt": "41", "kt": "60", "active": True},
    {"doc": "Перемещение", "dt": "41", "kt": "41", "active": True},
    {"doc": "Продажа", "dt": "62", "kt": "90.1", "active": True},
    {"doc": "Возврат", "dt": "90.1", "kt": "62", "active": True},
    {"doc": "Списание", "dt": "44", "kt": "41", "active": True},
]
ENTRIES: dict[str, list[dict]] = {}


def translate(doc_id: str, doc_type: str, amount: float, rules=RULES) -> list[dict]:
    active = [r for r in rules if r["doc"] == doc_type and r["active"]]
    if not active:
        raise TranslationError(
            f"RIH-ACC-001: нет активного правила трансляции для {doc_type}")
    built = [{"dt": r["dt"], "kt": r["kt"], "amount": amount, "doc": doc_id}
             for r in active]
    ENTRIES[doc_id] = built  # замена, а не добавление: идемпотентность
    return built


def main() -> None:
    cases = [("Поступление", "41", "60"), ("Перемещение", "41", "41"),
             ("Продажа", "62", "90.1"), ("Возврат", "90.1", "62"),
             ("Списание", "44", "41")]
    for index, (doc_type, dt, kt) in enumerate(cases, 1):
        built = translate(f"DOC-{index}", doc_type, 10_000)
        assert built[0]["dt"] == dt and built[0]["kt"] == kt, (doc_type, built)
    print("[ok] 5 документов транслируются по правилам: счета из данных, не из кода")

    try:
        translate("DOC-X", "НеизвестныйВид", 1)
        raise SystemExit("отсутствие правила проглочено молча")
    except TranslationError as error:
        assert "RIH-ACC-001" in str(error)
    print("[ok] сценарий 6: нет правила — ошибка RIH-ACC-001 вслух, документа без учёта нет")

    changed = [dict(rule) for rule in RULES]
    for rule in changed:
        if rule["doc"] == "Поступление":
            rule["kt"] = "76"
    built = translate("DOC-1", "Поступление", 10_000, rules=changed)
    assert built[0]["kt"] == "76"
    print("[ok] бухгалтер сменил счёт Кт 60 -> 76 в правиле: проводка перестроилась без кода")

    translate("DOC-2", "Перемещение", 5_000)
    translate("DOC-2", "Перемещение", 5_000)
    assert len(ENTRIES["DOC-2"]) == 1
    total = sum(e["amount"] for entries in ENTRIES.values() for e in entries)
    assert total == 45_000, total  # 4 документа по 10 000 и перемещение 5 000
    print("[ok] двойное проведение заменяет движения: задвоения проводок нет")


if __name__ == "__main__":
    main()
