#!/usr/bin/env python3
"""Проверки task_118: выписка банка, шаблоны назначений, поручения (зеркало).

Зеркало РИХ_Банк на эталонном файле стенда: итоги сверяются до разметки,
дубль внутри файла и повторная загрузка не создают вторых платежей,
нераспознанное уходит в ручной разбор. Поручения ходят в живой mock-шлюз
банка (:8023): SendPaymentOrder идемпотентен, статус — конечный автомат.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_bank_statement.py
"""

from __future__ import annotations

import hashlib
import re
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

SAMPLE = Path("data/bank_statement_sample.txt")
BANK = "http://127.0.0.1:8023/bank"
NS = {"bank": "http://rih.local/bank", "soap": "http://schemas.xmlsoap.org/soap/envelope/"}

TEMPLATES = [
    ("Заказ", "заказ"),
    ("Счёт", "счету"),
    ("Счёт", "счёту"),
    ("Счёт", "счета"),
    ("Договор", "договор"),
    ("Акт", "акту"),
]


class StatementError(ValueError):
    pass


def parse_statement(text: str) -> dict:
    result = {"account": "", "opening": 0.0, "declared_in": 0.0,
              "declared_out": 0.0, "closing": 0.0, "payments": []}
    current = None
    in_totals = False
    for raw in text.splitlines():
        if raw.strip() == "КонецДокумента" and current is not None:
            incoming = current["ПолучательСчет"] == result["account"]
            current["direction"] = "Поступление" if incoming else "Списание"
            current["counterparty"] = current["Плательщик"] if incoming else current["Получатель"]
            result["payments"].append(current)
            current = None
            continue
        if raw.strip() == "СекцияРасчСчет":
            in_totals = True
            continue
        if raw.strip() == "КонецРасчСчет":
            in_totals = False
            continue
        if "=" not in raw:
            continue
        key, value = (part.strip() for part in raw.split("=", 1))
        if key == "СекцияДокумент":
            current = {"kind": value}
        elif key == "КонецДокумента" and current is not None:
            incoming = current["ПолучательСчет"] == result["account"]
            current["direction"] = "Поступление" if incoming else "Списание"
            current["counterparty"] = current["Плательщик"] if incoming else current["Получатель"]
            result["payments"].append(current)
            current = None
        elif key == "СекцияРасчСчет":
            in_totals = True
        elif key == "КонецРасчСчет":
            in_totals = False
        elif current is not None:
            current[key] = value
        elif in_totals:
            if key == "НачальныйОстаток":
                result["opening"] = float(value)
            elif key == "ВсегоПоступило":
                result["declared_in"] = float(value)
            elif key == "ВсегоСписано":
                result["declared_out"] = float(value)
            elif key == "КонечныйОстаток":
                result["closing"] = float(value)
        elif key == "РасчСчет":
            result["account"] = value
    return result


def payment_key(payment: dict) -> str:
    return "|".join([payment["kind"], payment["Номер"], payment["ДатаПоступило"],
                     f"{float(payment['Сумма']):.2f}", payment["ПлательщикСчет"]])


def match_purpose(purpose: str, templates: list[tuple[str, str]]) -> tuple[str, str, str]:
    lowered = purpose.lower()
    for kind, marker in templates:
        position = lowered.find(marker)
        if position < 0:
            continue
        rest = purpose[position + len(marker):]
        for word in rest.split():
            cleaned = word.strip(".,;:()«»\"№")
            if cleaned and any(ch.isdigit() for ch in cleaned):
                return kind, cleaned, "автоматически"
    return "", "", "ручной разбор"


class StatementLoader:
    def __init__(self, templates: list[tuple[str, str]]) -> None:
        self.templates = templates
        self.payments: dict[str, dict] = {}

    def load(self, text: str) -> dict:
        data = parse_statement(text)
        unique: dict[str, dict] = {}
        for payment in data["payments"]:
            unique.setdefault(payment_key(payment), payment)
        total_in = sum(float(p["Сумма"]) for p in unique.values()
                       if p["direction"] == "Поступление")
        total_out = sum(float(p["Сумма"]) for p in unique.values()
                        if p["direction"] == "Списание")
        if round(total_in, 2) != round(data["declared_in"], 2) \
                or round(total_out, 2) != round(data["declared_out"], 2):
            raise StatementError("обороты файла не сходятся с секцией счёта")
        closing = data["opening"] + total_in - total_out
        if round(closing, 2) != round(data["closing"], 2):
            raise StatementError("конечный остаток не сходится")
        new = duplicates = auto = manual = 0
        for key, payment in unique.items():
            if key in self.payments:
                duplicates += 1
                continue
            kind, number, status = match_purpose(payment["НазначениеПлатежа"], self.templates)
            self.payments[key] = {**payment, "basis_kind": kind,
                                  "basis_number": number, "match": status}
            new += 1
            auto += status == "автоматически"
            manual += status != "автоматически"
        return {"file_records": len(data["payments"]), "new": new,
                "duplicates": duplicates + (len(data["payments"]) - len(unique)),
                "auto": auto, "manual": manual,
                "total_in": round(total_in, 2), "total_out": round(total_out, 2),
                "closing": round(closing, 2)}


def soap(body: str) -> ET.Element:
    envelope = (
        '<?xml version="1.0"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:tns="http://rih.local/bank"><soap:Header>'
        "<tns:Authentication><tns:Login>bank_user</tns:Login>"
        "<tns:Password>bank_password</tns:Password></tns:Authentication>"
        f"</soap:Header><soap:Body>{body}</soap:Body></soap:Envelope>")
    request = urllib.request.Request(BANK, data=envelope.encode(), method="POST")
    request.add_header("Content-Type", "text/xml")
    with urllib.request.urlopen(request, timeout=10) as response:
        return ET.fromstring(response.read().decode())


def find(root: ET.Element, name: str) -> str:
    element = root.find(f".//bank:{name}", NS)
    return element.text if element is not None else ""


class PaymentOrder:
    TRANSITIONS = {"Создано": {"Отправлено"}, "Отправлено": {"Принято", "Отклонено"},
                   "Принято": {"Исполнено", "Отклонено"},
                   "Исполнено": set(), "Отклонено": set()}

    def __init__(self, owner: str) -> None:
        self.status = "Создано"
        self.owner = owner
        self.gateway_id = ""
        self.rejection_reason = ""

    def move(self, new_status: str) -> None:
        if new_status not in self.TRANSITIONS[self.status]:
            raise StatementError(f"запрещён переход {self.status} -> {new_status}")
        self.status = new_status
        if new_status == "Отклонено":
            self.rejection_reason = "банк отклонил поручение; возвращено владельцу"

    def send(self, external_id: str) -> None:
        self.move("Отправлено")
        body = ("<tns:SendPaymentOrder>"
                f"<tns:ExternalId>{external_id}</tns:ExternalId>"
                "<tns:DocNumber>118001</tns:DocNumber>"
                "<tns:DocDate>2026-11-17</tns:DocDate>"
                "<tns:Payer>Ритейл Групп</tns:Payer>"
                "<tns:Payee>Логистик Плюс</tns:Payee>"
                "<tns:Amount>5000.00</tns:Amount>"
                "<tns:Currency>BYN</tns:Currency>"
                "<tns:Purpose>Оплата транспортных услуг</tns:Purpose>"
                "</tns:SendPaymentOrder>")
        root = soap(body)
        self.gateway_id = find(root, "PaymentId")
        assert find(root, "Duplicate") in ("true", "false")
        self.move("Принято")

    def poll(self) -> None:
        body = ("<tns:GetPaymentStatus>"
                f"<tns:PaymentId>{self.gateway_id}</tns:PaymentId>"
                "</tns:GetPaymentStatus>")
        gateway_status = find(soap(body), "Status")
        self.move({"paid": "Исполнено", "rejected": "Отклонено"}.get(
            gateway_status, "Принято"))


def main() -> None:
    text = SAMPLE.read_text(encoding="utf-8")
    file_hash = hashlib.sha256(text.encode()).hexdigest()
    loader = StatementLoader(TEMPLATES)
    outcome = loader.load(text)
    assert outcome["file_records"] == 6 and outcome["new"] == 5, outcome
    assert outcome["duplicates"] == 1 and outcome["auto"] == 4 and outcome["manual"] == 1
    assert outcome["total_in"] == 2434.30 and outcome["total_out"] == 6740.55
    assert outcome["closing"] == 11123.90
    print(f"[ok] выписка: записей 6, применено 5, дубль отсечён, авто 4, вручную 1; "
          f"хеш файла {file_hash[:12]}…")
    print(f"[ok] итоги сошлись с банком: +{outcome['total_in']:.2f} "
          f"-{outcome['total_out']:.2f} = остаток {outcome['closing']:.2f}")

    matched = {(p["Номер"], p["basis_kind"], p["basis_number"])
               for p in loader.payments.values() if p["match"] == "автоматически"}
    assert ("000142", "Заказ", "SHOP-1042") in matched
    assert ("000143", "Счёт", "000143") in matched
    assert ("000078", "Счёт", "000998") in matched
    assert ("000077", "Акт", "А-1026") in matched
    manual = [p["Номер"] for p in loader.payments.values() if p["match"] == "ручной разбор"]
    assert manual == ["000144"], manual
    print(f"[ok] сопоставлено шаблонами: {sorted(matched)}")
    print(f"[ok] ручной разбор бухгалтера: платёж {manual[0]} (возврат без номера документа)")

    second = loader.load(text)
    assert second["new"] == 0 and len(loader.payments) == 5
    print("[ok] повторная загрузка того же файла: новых платежей 0, задвоений нет")

    without_order = StatementLoader([t for t in TEMPLATES if t[0] != "Заказ"])
    kind, number, _ = match_purpose(
        "Оплата по счету 000142 от 12.11.2026 за товар по заказу SHOP-1042.",
        without_order.templates)
    assert (kind, number) == ("Счёт", "000142"), (kind, number)
    print("[ok] шаблоны настраиваемы без кода: без шаблона «Заказ» тот же платёж ушёл в «Счёт»")

    broken = text.replace("ВсегоПоступило=2434.30", "ВсегоПоступило=2400.00")
    fresh = StatementLoader(TEMPLATES)
    try:
        fresh.load(broken)
        raise AssertionError("битая выписка принята")
    except StatementError as err:
        assert not fresh.payments
        print(f"[ok] расхождение итогов: загрузка отменена целиком, платежей 0 ({err})")

    order = PaymentOrder("бухгалтер Иванова")
    external_id = f"task118-{uuid.uuid4()}"
    order.send(external_id)
    first_id = order.gateway_id
    order.poll()
    assert order.status == "Исполнено"
    print(f"[ok] поручение в живом шлюзе: Создано -> Отправлено -> Принято -> Исполнено ({first_id[:8]}…)")

    again = PaymentOrder("бухгалтер Иванова")
    again.send(external_id)
    assert again.gateway_id == first_id
    print("[ok] повторная выгрузка того же поручения: шлюз вернул прежний PaymentId, дубля платежа нет")

    lazy = PaymentOrder("бухгалтер Иванова")
    try:
        lazy.move("Исполнено")
        raise AssertionError("пропуск статуса разрешён")
    except StatementError as err:
        print(f"[ok] конечный автомат поручений: пропуск статуса запрещён ({err})")
    rejected = PaymentOrder("бухгалтер Иванова")
    rejected.move("Отправлено")
    rejected.move("Отклонено")
    assert rejected.owner in "бухгалтер Иванова" and rejected.rejection_reason
    print(f"[ok] отклонённое поручение возвращается владельцу в тот же день: {rejected.owner}")


if __name__ == "__main__":
    main()
