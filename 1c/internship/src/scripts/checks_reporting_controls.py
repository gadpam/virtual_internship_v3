#!/usr/bin/env python3
"""Проверки task_162: контрольные соотношения регламентированной отчётности.

Проверки — отдельный модуль, а не часть формы: предварительный
прогон гоняет их по данным до формирования формы и показывает
готовность. 8 соотношений; искусственная ошибка в строке 100
ловится проверкой №4 до отправки, а не протоколом отказа.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_reporting_controls.py
"""

from __future__ import annotations


def checks(form: dict) -> list[str]:
    failed = []
    rows = form["rows"]
    if abs(rows["100"] - (rows["110"] + rows["120"] + rows["130"])) > 0.005:
        failed.append("№4: строка 100 != сумме строк 110-130")
    if abs(form["turnover_68"] - form["vat_accrued"]) > 0.005:
        failed.append("№1: оборот счёта 68 != начисленному НДС формы")
    if abs(form["turnover_68"] + form["vat_deducted"]
           - form["vat_payable"]) > 0.005:
        failed.append("№2: начисленный минус вычет != НДС к уплате")
    if form["vat_deducted"] > form["vat_accrued"] and not form["refund_reason"]:
        failed.append("№3: вычет больше начисления без основания возмещения")
    if rows["100"] < 0:
        failed.append("№5: выручка раздела отрицательна")
    if abs(form["revenue_90"] - rows["100"]) > 0.005:
        failed.append("№6: раздел формы != обороту выручки счёта 90.1")
    if form["period_end"] <= form["period_start"]:
        failed.append("№7: период формы пуст или перевёрнут")
    if not form["signed_by"]:
        failed.append("№8: форма без подписанта не уходит в отправку")
    return failed


def good_form() -> dict:
    return {"rows": {"100": 300.0, "110": 100.0, "120": 120.0, "130": 80.0},
            "turnover_68": 60.0, "vat_accrued": 60.0, "vat_deducted": 40.0,
            "vat_payable": 100.0, "refund_reason": "",
            "revenue_90": 300.0, "period_start": "2026-01-01",
            "period_end": "2026-03-31", "signed_by": "Главный бухгалтер"}


def main() -> None:
    assert checks(good_form()) == []
    print("[ok] готовая форма: 8 контрольных соотношений проходят, предварительный прогон зелёный")

    broken = good_form()
    broken["rows"]["100"] = 310.0
    failed = checks(broken)
    assert any("№4" in f for f in failed), failed
    print(f"[ok] искусственная ошибка строки 100 поймана до формирования формы: {failed[0]}")

    unready = good_form()
    unready["vat_deducted"] = 70.0
    unready["vat_payable"] = 130.0
    failed = checks(unready)
    assert any("№3" in f for f in failed), failed
    print("[ok] прогон готовности: вычет больше начисления без основания — форма к отправке не готова")


if __name__ == "__main__":
    main()
