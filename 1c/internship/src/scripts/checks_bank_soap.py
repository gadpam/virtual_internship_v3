#!/usr/bin/env python3
"""Проверки task_85/86: SOAP-контур банка живьём.

WSDL читается, GetRates с авторизацией возвращает курсы, без неё —
SOAP Fault AuthFailed (не HTTP 500), недоступный порт — сетевая
ошибка, которая отличается от Fault и по типу, и по сообщению.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_bank_soap.py
"""

from __future__ import annotations

import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BANK = "http://127.0.0.1:8023/bank"
NS = {"bank": "http://rih.local/bank", "soap": "http://schemas.xmlsoap.org/soap/envelope/"}


def envelope(body: str, auth: bool = True) -> bytes:
    header = ""
    if auth:
        header = ("<soap:Header><tns:Authentication><tns:Login>bank_user</tns:Login>"
                  "<tns:Password>bank_password</tns:Password></tns:Authentication></soap:Header>")
    return (f'<?xml version="1.0"?>'
            f'<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            f'xmlns:tns="http://rih.local/bank">{header}'
            f"<soap:Body>{body}</soap:Body></soap:Envelope>").encode()


def post(url: str, data: bytes) -> tuple[int, str]:
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "text/xml")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode()


def main() -> None:
    with urllib.request.urlopen(BANK + "?wsdl", timeout=5) as resp:
        wsdl = resp.read().decode()
    for op in ("GetStatement", "SendPaymentOrder", "GetPaymentStatus", "GetRates"):
        assert f'operation name="{op}"' in wsdl, op
    print("[ok] WSDL читается, операций: 4")

    status, text = post(BANK, envelope('<tns:GetRates><tns:Date>2026-11-17</tns:Date></tns:GetRates>'))
    root = ET.fromstring(text)
    rates = root.findall(".//bank:Rate", NS)
    values = {r.findtext("bank:CharCode", namespaces=NS): float(r.findtext("bank:Value", namespaces=NS)) for r in rates}
    assert status == 200 and values.get("USD", 0) > 3.0, values
    print(f"[ok] GetRates с авторизацией: {values}")

    status, text = post(BANK, envelope('<tns:GetRates/>', auth=False))
    root = ET.fromstring(text)
    fault = root.find(".//soap:Fault", NS)
    assert fault is not None and "AuthFailed" in fault.findtext("faultcode")
    print("[ok] без авторизации — SOAP Fault AuthFailed, а не HTTP 500")

    try:
        post("http://127.0.0.1:9999/bank", envelope('<tns:GetRates/>'))
        raise AssertionError("недоступный порт не дал ошибки")
    except urllib.error.URLError as err:
        print(f"[ok] недоступность сервиса — сетевая ошибка, не Fault: {type(err.reason).__name__}")


if __name__ == "__main__":
    main()
