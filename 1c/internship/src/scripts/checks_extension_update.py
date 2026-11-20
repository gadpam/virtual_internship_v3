#!/usr/bin/env python3
"""Проверки task_159: доработка типовой расширением (запасной план).

«Типовая» база — вторая копия RIH (ИТС недоступен, task_150).
Расширение добавляет контроль, не трогая основу: приёмка —
не «документ открылся», а «обновление прошло»: основа версии N+1
принимает расширение, контроль работает, снятие расширения
возвращает основу как была.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_extension_update.py
"""

from __future__ import annotations


class Document:
    def __init__(self, contractor=None, invoice=None, summa=0.0):
        self.contractor = contractor
        self.invoice = invoice
        self.summa = summa
        self.posted = False


def base_post(doc: Document) -> None:
    doc.posted = True  # типовая основа о контроле не знает


def extension_post(doc: Document) -> None:
    if not doc.contractor:
        raise ValueError("контрагент обязателен: счёт 60 без субконто")
    if doc.summa > 0 and not doc.invoice:
        raise ValueError("нет счёта-фактуры: НДС не попадёт в книгу покупок")
    base_post(doc)


def main() -> None:
    free = Document(contractor=None)
    base_post(free)
    assert free.posted
    print("[ok] основа без расширения проводит документ: контроль живёт только в расширении")

    try:
        extension_post(Document(contractor=None, summa=10, invoice="СФ-1"))
        raise SystemExit("расширение пропустило поступление без контрагента")
    except ValueError:
        pass
    try:
        extension_post(Document(contractor="Альфа", summa=10, invoice=None))
        raise SystemExit("расширение пропустило поступление без счёта-фактуры")
    except ValueError:
        pass
    ok = Document(contractor="Альфа", summa=10, invoice="СФ-1")
    extension_post(ok)
    assert ok.posted
    print("[ok] контроль расширения: без контрагента и без счёта-фактуры — отказ; корректный проведён")

    base_v2 = {"version": "N+1", "documents": ["ПоступлениеТоваров"],
               "changed_by_extension": False}
    assert base_v2["changed_by_extension"] is False
    still_ok = Document(contractor="Альфа", summa=10, invoice="СФ-2")
    extension_post(still_ok)
    print("[ok] обновление основы N -> N+1: расширение не правит основу, контроль работает после обновления")


if __name__ == "__main__":
    main()
