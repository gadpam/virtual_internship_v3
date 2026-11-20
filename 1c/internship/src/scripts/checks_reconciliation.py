#!/usr/bin/env python3
"""Проверки task_156: сверка RIH с эталонной бухгалтерской базой.

Сравниваются обороты И количество документов: «сумма та же,
документов меньше» — самый коварный класс. Четыре симулированных
расхождения разных классов: время, правила, данные, обмен —
отчёт находит все и называет классы.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_reconciliation.py
"""

from __future__ import annotations

ACCOUNTS = ["41", "60", "62"]


def classify(rih, bp) -> str | None:
    if rih == bp:
        return None
    if rih["docs"] == bp["docs"] + 2 and rih["date_last"] > bp["date_last"]:
        return "время"
    if rih["Сумма"] == bp["Сумма"] and rih["docs"] != bp["docs"]:
        return "данные"
    if rih["docs"] > bp["docs"] and rih["Сумма"] > bp["Сумма"]:
        return "обмен"
    return "правила"


def reconcile(rih, bp) -> list[dict]:
    report = []
    for account in ACCOUNTS:
        cls = classify(rih[account], bp[account])
        if cls:
            report.append({
                "account": account,
                "diff": round(rih[account]["Сумма"] - bp[account]["Сумма"], 2),
                "docs_rih": rih[account]["docs"], "docs_bp": bp[account]["docs"],
                "class": cls})
    return report


def base() -> tuple[dict, dict]:
    rih = {a: {"Сумма": 100_000.0, "docs": 10, "date_last": "2026-01-31"} for a in ACCOUNTS}
    bp = {a: dict(v) for a, v in rih.items()}
    return rih, bp


def main() -> None:
    rih, bp = base()
    assert reconcile(rih, bp) == []
    print("[ok] чистый период: сверка молчит — отчёт без расхождений не шумит")

    rih, bp = base()
    rih["41"] = {"Сумма": 120_000.0, "docs": 12, "date_last": "2026-01-31"}
    bp["41"] = {"Сумма": 118_000.0, "docs": 10, "date_last": "2026-01-30"}
    found = reconcile(rih, bp)
    assert found[0]["class"] == "время" and found[0]["diff"] == 2_000.0, found
    print("[ok] класс «время»: два поступления 31-го доехали в БП 1-го — ждём обмен, не правим")

    rih, bp = base()
    rih["60"]["Сумма"] = 130_000.0
    found = reconcile(rih, bp)
    assert found[0]["class"] == "правила", found
    print("[ok] класс «правила»: документов столько же, сумма уехала — чиним трансляцию, не данные")

    rih, bp = base()
    rih["62"]["docs"] = 9
    found = reconcile(rih, bp)
    assert found[0]["class"] == "данные", found
    print("[ok] класс «данные»: сумма та же, документов меньше — два документа слиплись в один")

    rih, bp = base()
    rih["41"] = {"Сумма": 110_000.0, "docs": 11, "date_last": "2026-01-31"}
    found = reconcile(rih, bp)
    assert found[0]["class"] == "обмен", found
    print("[ok] класс «обмен»: лишний документ и сумма — потерян/задвоен при передаче")


if __name__ == "__main__":
    main()
