#!/usr/bin/env python3
"""Проверки task_119: форма ПРОД-25, КС, квитанции, корректировки (зеркало).

Зеркало РИХ_ОтраслевыеОтчёты: форма из данных продаж, семь контрольных
соотношений до отправки, файл+хеш, имитация оператора, отклонение,
корректирующая версия со ссылкой и неизменность отправленной версии.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_industry_report.py
"""

from __future__ import annotations

import copy
import hashlib
import json

KNOWN_SHOPS = {"SHOP-1", "SHOP-2", "SHOP-3", "MAG-2"}
PERIOD = ("2026-11-01", "2026-11-30")


class ReportError(ValueError):
    pass


def build_form(rows: list[dict]) -> dict:
    totals = {"sales": 0.0, "returns": 0.0, "net": 0.0,
              "receipts": 0, "returnReceipts": 0}
    for row in rows:
        row["net"] = round(row["sales"] - row["returns"], 2)
        for key in totals:
            totals[key] += row[key]
    return {"form": "ПРОД-25", "periodFrom": PERIOD[0], "periodTo": PERIOD[1],
            "recipients": len(rows), "stores": rows, "totals": totals}


def check_form(form: dict) -> list[str]:
    errors: list[str] = []
    for row in form["stores"]:
        if row["shop"] not in KNOWN_SHOPS:
            errors.append(f"КС-01: магазин не найден в справочнике: {row['shop']}")
        if round(row["net"], 2) != round(row["sales"] - row["returns"], 2):
            errors.append(f"КС-02: чистая выручка не сходится у магазина {row['shop']}")
        if row["sales"] < 0 or row["returns"] < 0 or row["receipts"] < 0 \
                or row["returnReceipts"] < 0:
            errors.append(f"КС-06: отрицательный показатель у магазина {row['shop']}")
        if round(row["returns"], 2) > round(row["sales"], 2):
            errors.append(f"КС-07: возвраты выше продаж у магазина {row['shop']}")
    if round(sum(r["sales"] for r in form["stores"]), 2) != round(form["totals"]["sales"], 2) \
            or round(sum(r["returns"] for r in form["stores"]), 2) != round(form["totals"]["returns"], 2) \
            or sum(r["receipts"] for r in form["stores"]) != form["totals"]["receipts"]:
        errors.append("КС-03: итоги раздела Б не равны суммам раздела А")
    if form["recipients"] <= 0 or form["recipients"] != len(form["stores"]):
        errors.append("КС-05: количество получателей не равно числу магазинов")
    return errors


def check_period(form: dict, period: tuple[str, str]) -> str:
    if (form["periodFrom"], form["periodTo"]) != period:
        return "КС-04: период формы не совпадает с периодом выгрузки"
    return ""


def export_file(form: dict) -> tuple[str, str]:
    text = json.dumps(form, ensure_ascii=False, sort_keys=True)
    return text, hashlib.sha256(text.encode()).hexdigest()


def operator_gateway(form: dict, file_hash: str, sequence: int) -> dict:
    for row in form["stores"]:
        if not row["shop"].startswith("SHOP-"):
            return {"receipt": f"ПР-{sequence:04d}", "result": "Отклонён",
                    "report_status": "ТребуетсяКорректировка",
                    "protocol": f"КС-01 оператора: магазин не сопоставлен реестру: {row['shop']}"}
    return {"receipt": f"КВ-{sequence:04d}", "result": "Принят",
            "report_status": "Принят", "protocol": "контрольные соотношения пройдены"}


class ReportFlow:
    def __init__(self) -> None:
        self.versions: dict[int, dict] = {}
        self.receipts: dict[str, dict] = {}
        self.next_id = 1
        self.gateway_sequence = 0

    def create(self, form: dict, previous: int | None = None, reason: str = "") -> int:
        report_id = self.next_id
        self.next_id += 1
        version = 1 if previous is None else self.versions[previous]["version"] + 1
        self.versions[report_id] = {"id": report_id, "version": version,
                                    "form": copy.deepcopy(form), "status": "Черновик",
                                    "previous": previous, "reason": reason,
                                    "file_hash": "", "locked": False}
        return report_id

    def send(self, report_id: int) -> dict:
        report = self.versions[report_id]
        if report["status"] != "Черновик":
            raise ReportError(f"отправить можно только черновик: {report['status']}")
        errors = check_form(report["form"])
        period_error = check_period(report["form"], PERIOD)
        if period_error:
            errors.append(period_error)
        if errors:
            raise ReportError("форма не прошла проверки: " + "; ".join(errors))
        _, file_hash = export_file(report["form"])
        report["file_hash"] = file_hash
        report["status"] = "Отправлен"
        report["locked"] = True
        self.gateway_sequence += 1
        answer = operator_gateway(report["form"], file_hash, self.gateway_sequence)
        report["status"] = answer["report_status"] if answer["result"] == "Отклонён" else "Принят"
        if answer["result"] == "Принят":
            report["status"] = "Принят"
        self.receipts[answer["receipt"]] = {"report": report_id,
                                            "result": answer["result"],
                                            "file_hash": file_hash,
                                            "protocol": answer["protocol"]}
        return answer

    def correct(self, report_id: int, reason: str, fixed_form: dict) -> int:
        report = self.versions[report_id]
        if report["status"] not in ("Отклонён", "ТребуетсяКорректировка"):
            raise ReportError("корректировка возможна только после отклонения")
        if not reason.strip():
            raise ReportError("у корректировки обязательна причина")
        if report["locked"]:
            _, current_hash = export_file(report["form"])
            assert current_hash == report["file_hash"], "отправленная версия изменена"
        return self.create(fixed_form, previous=report_id, reason=reason)

    def history(self, report_id: int) -> list[int]:
        chain = []
        current = report_id
        while current is not None:
            chain.insert(0, current)
            current = self.versions[current]["previous"]
        return chain


def sample_rows() -> list[dict]:
    return [
        {"shop": "SHOP-1", "sales": 120000.0, "returns": 3000.0, "receipts": 940, "returnReceipts": 21},
        {"shop": "SHOP-2", "sales": 86000.0, "returns": 1200.0, "receipts": 655, "returnReceipts": 9},
        {"shop": "SHOP-3", "sales": 43200.0, "returns": 0.0, "receipts": 301, "returnReceipts": 0},
    ]


def expect_rule(mutate, code: str) -> None:
    form = build_form(sample_rows())
    mutate(form)
    errors = check_form(form) + ([check_period(form, PERIOD)] if code == "КС-04" else [])
    assert any(err.startswith(code) for err in errors), (code, errors)


def main() -> None:
    form = build_form(sample_rows())
    assert check_form(form) == [] and check_period(form, PERIOD) == ""
    assert form["totals"]["sales"] == 249200.0 and form["totals"]["net"] == 245000.0
    assert form["recipients"] == 3 and form["totals"]["receipts"] == 1896
    print(f"[ok] форма из данных: 3 магазина, продажи {form['totals']['sales']:.2f}, "
          f"чистая {form['totals']['net']:.2f}, чеков {form['totals']['receipts']}")

    expect_rule(lambda f: f["stores"][0].update(net=1.0), "КС-02")
    expect_rule(lambda f: f["totals"].update(sales=1.0), "КС-03")
    expect_rule(lambda f: f.update(periodTo="2026-11-29"), "КС-04")
    expect_rule(lambda f: f.update(recipients=2), "КС-05")
    expect_rule(lambda f: f["stores"][1].update(sales=-5.0), "КС-06")
    expect_rule(lambda f: f["stores"][2].update(returns=99999.0), "КС-07")
    expect_rule(lambda f: f["stores"][0].update(shop="SHOP-99"), "КС-01")
    print("[ok] контрольные соотношения: все 7 правил по отдельности ловят свою ошибку")

    text, file_hash = export_file(form)
    assert json.loads(text)["form"] == "ПРОД-25" and len(file_hash) == 64
    print(f"[ok] выгрузка: файл JSON, SHA-256 {file_hash[:12]}… — пара для квитанции")

    flow = ReportFlow()
    clean_id = flow.create(build_form(sample_rows()))
    answer = flow.send(clean_id)
    assert answer["result"] == "Принят" and flow.versions[clean_id]["status"] == "Принят"
    assert flow.receipts[answer["receipt"]]["file_hash"] == flow.versions[clean_id]["file_hash"]
    print(f"[ok] отправка принята, квитанция {answer['receipt']} хранится с хешем файла")

    bad_rows = sample_rows()
    bad_rows[1] = {**bad_rows[1], "shop": "MAG-2"}
    bad_id = flow.create(build_form(bad_rows))
    answer = flow.send(bad_id)
    assert answer["result"] == "Отклонён"
    assert flow.versions[bad_id]["status"] == "ТребуетсяКорректировка"
    print(f"[ok] оператор отклонил: {answer['protocol']}; статус — ТребуетсяКорректировка")

    fixed_rows = sample_rows()
    fixed_id = flow.correct(bad_id, "код магазина сопоставлен реестру оператора", build_form(fixed_rows))
    assert flow.versions[fixed_id]["version"] == 2
    assert flow.versions[fixed_id]["previous"] == bad_id
    answer2 = flow.send(fixed_id)
    assert answer2["result"] == "Принят"
    assert flow.history(fixed_id) == [bad_id, fixed_id]
    print(f"[ok] корректировка v2 принята (квитанция {answer2['receipt']}); история версий сохранена")

    _, hash_after = export_file(flow.versions[bad_id]["form"])
    assert hash_after == flow.versions[bad_id]["file_hash"]
    print("[ok] отправленная v1 не перезаписана: хеш файла прежний, исправляла только v2")


if __name__ == "__main__":
    main()
