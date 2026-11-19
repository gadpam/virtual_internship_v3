"""Mock SOAP-сервис банка (task_85, task_86, task_94, task_140).

Минимальная реализация SOAP 1.1 без внешних библиотек: разбор XML через
xml.etree, генерация ответа и SOAP Fault вручную. Это сделано намеренно —
стабильно работает на любом стенде и показывает «настоящий» XML-контракт.
"""
import os
import random
import uuid
import xml.etree.ElementTree as ET
from datetime import date, datetime
from typing import Dict, Optional, Tuple

from fastapi import FastAPI, Header, Request, Response

LOGIN = os.getenv("MOCK_BANK_LOGIN", "bank_user")
PASSWORD = os.getenv("MOCK_BANK_PASSWORD", "bank_password")

NS = "http://rih.local/bank"
SOAP = "http://schemas.xmlsoap.org/soap/envelope/"
WSDL = "http://rih.local/bank/wsdl"

app = FastAPI(title="Mock Bank SOAP WS", version="1.0.0")

PAYMENTS: Dict[str, dict] = {}


class SoapFault(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _strip_ns(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def _text(element: Optional[ET.Element], name: str, default: str = "") -> str:
    if element is None:
        return default
    for child in element:
        if _strip_ns(child.tag) == name:
            return (child.text or "").strip()
    return default


def _envelope(body_xml: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<soapenv:Envelope xmlns:soapenv="{SOAP}" xmlns:bank="{NS}">'
        "<soapenv:Body>"
        f"{body_xml}"
        "</soapenv:Body>"
        "</soapenv:Envelope>"
    )


def _fault(code: str, message: str) -> str:
    safe = message.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return _envelope(
        "<soapenv:Fault>"
        f"<faultcode>soapenv:Server.{code}</faultcode>"
        "<faultstring>" + safe + "</faultstring>"
        "</soapenv:Fault>"
    )


def _seed_payments(count: int = 40) -> None:
    if PAYMENTS:
        return
    counterparties = ["ООО «Ромашка»", "УП «Вектор»", "ИП Сидоров А.А.", "ОАО «Белтранс»"]
    purposes = ["Оплата по счёту №%d", "Арендная плата за январь", "Возврат по претензии №%d", "Услуги связи"]
    today = date.today()
    for index in range(count):
        payment_id = str(uuid.uuid4())
        PAYMENTS[payment_id] = {
            "paymentId": payment_id,
            "docNumber": f"{index + 1:05d}",
            "docDate": today.isoformat(),
            "payer": random.choice(counterparties),
            "payee": "ОАО «Учебный Банк»",
            "amount": round(random.uniform(50.0, 25000.0), 2),
            "currency": "BYN",
            "purpose": random.choice(purposes) % (index + 1) if "%d" in random.choice(purposes) else "Оплата по договору",
            "status": random.choice(["accepted", "processing", "paid", "rejected"]),
        }


_seed_payments()


def _handle_get_statement(body: ET.Element) -> str:
    date_from = _text(body, "DateFrom")
    date_to = _text(body, "DateTo")
    if date_from and date_to and date_from > date_to:
        raise SoapFault("InvalidPeriod", f"Дата начала {date_from} больше даты конца {date_to}")

    rows = []
    for payment in list(PAYMENTS.values())[:25]:
        if date_from and payment["docDate"] < date_from:
            continue
        if date_to and payment["docDate"] > date_to:
            continue
        rows.append(
            "<bank:Payment>"
            f"<bank:PaymentId>{payment['paymentId']}</bank:PaymentId>"
            f"<bank:DocNumber>{payment['docNumber']}</bank:DocNumber>"
            f"<bank:DocDate>{payment['docDate']}</bank:DocDate>"
            f"<bank:Payer>{payment['payer']}</bank:Payer>"
            f"<bank:Amount>{payment['amount']}</bank:Amount>"
            f"<bank:Currency>{payment['currency']}</bank:Currency>"
            f"<bank:Status>{payment['status']}</bank:Status>"
            "</bank:Payment>"
        )
    return (
        "<bank:GetStatementResponse>"
        f"<bank:DateFrom>{date_from or ''}</bank:DateFrom>"
        f"<bank:DateTo>{date_to or ''}</bank:DateTo>"
        f"<bank:Total>{len(rows)}</bank:Total>"
        "<bank:Payments>" + "".join(rows) + "</bank:Payments>"
        "</bank:GetStatementResponse>"
    )


def _handle_send_payment_order(body: ET.Element) -> str:
    external_id = _text(body, "ExternalId")
    amount_text = _text(body, "Amount", "0")
    try:
        amount = float(amount_text)
    except ValueError:
        raise SoapFault("InvalidAmount", f"Сумма '{amount_text}' не является числом")
    if amount <= 0:
        raise SoapFault("InvalidAmount", "Сумма платёжного поручения должна быть больше нуля")

    existing = next((p for p in PAYMENTS.values() if p.get("externalId") == external_id), None)
    if existing:
        payment_id, duplicate = existing["paymentId"], "true"
    else:
        payment_id = str(uuid.uuid4())
        PAYMENTS[payment_id] = {
            "paymentId": payment_id, "externalId": external_id,
            "docNumber": _text(body, "DocNumber") or f"{len(PAYMENTS) + 1:05d}",
            "docDate": _text(body, "DocDate") or date.today().isoformat(),
            "payer": _text(body, "Payer") or "Ритейл Групп",
            "payee": _text(body, "Payee") or "Контрагент",
            "amount": amount, "currency": _text(body, "Currency") or "BYN",
            "purpose": _text(body, "Purpose") or "Оплата по договору",
            "status": "processing",
        }
        duplicate = "false"

    return (
        "<bank:SendPaymentOrderResponse>"
        f"<bank:PaymentId>{payment_id}</bank:PaymentId>"
        f"<bank:Status>processing</bank:Status>"
        f"<bank:Duplicate>{duplicate}</bank:Duplicate>"
        "</bank:SendPaymentOrderResponse>"
    )


def _handle_get_payment_status(body: ET.Element) -> str:
    payment_id = _text(body, "PaymentId")
    payment = PAYMENTS.get(payment_id)
    if not payment:
        raise SoapFault("NotFound", f"Платёж {payment_id} не найден")
    order = ["processing", "paid"]
    if payment["status"] == "processing":
        payment["status"] = "paid"
    return (
        "<bank:GetPaymentStatusResponse>"
        f"<bank:PaymentId>{payment_id}</bank:PaymentId>"
        f"<bank:Status>{payment['status']}</bank:Status>"
        f"<bank:Amount>{payment['amount']}</bank:Amount>"
        "</bank:GetPaymentStatusResponse>"
    )


def _handle_get_rates(body: ET.Element) -> str:
    on_date = _text(body, "Date") or date.today().isoformat()
    rows = []
    for code, nominal, base in (("USD", 1, 3.21), ("EUR", 1, 3.48), ("RUB", 100, 3.42), ("CNY", 10, 4.44)):
        rate = round(base * random.uniform(0.995, 1.005), 4)
        rows.append(
            "<bank:Rate>"
            f"<bank:Date>{on_date}</bank:Date>"
            f"<bank:CharCode>{code}</bank:CharCode>"
            f"<bank:Nominal>{nominal}</bank:Nominal>"
            f"<bank:Value>{rate}</bank:Value>"
            "</bank:Rate>"
        )
    return "<bank:GetRatesResponse>" + "".join(rows) + "</bank:GetRatesResponse>"


HANDLERS = {
    "GetStatement": _handle_get_statement,
    "SendPaymentOrder": _handle_send_payment_order,
    "GetPaymentStatus": _handle_get_payment_status,
    "GetRates": _handle_get_rates,
}


def _authenticate(header: Optional[ET.Element]) -> None:
    auth = None
    if header is not None:
        for child in header:
            if _strip_ns(child.tag) == "Authentication":
                auth = child
    login = _text(auth, "Login")
    password = _text(auth, "Password")
    if login != LOGIN or password != PASSWORD:
        raise SoapFault("AuthFailed", "Неверный логин или пароль банковского сервиса")


@app.get("/bank")
def wsdl(x_fault_mode: Optional[str] = Header(default=None)) -> Response:
    """Отдаёт упрощённый WSDL, чтобы клиент 1С/Python мог прочитать контракт."""
    operations = "".join(
        f'<wsdl:operation name="{name}"><wsdl:input message="tns:{name}In"/>'
        f'<wsdl:output message="tns:{name}Out"/></wsdl:operation>'
        for name in HANDLERS
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<wsdl:definitions xmlns:wsdl="http://schemas.xmlsoap.org/wsdl/" '
        'xmlns:soap="http://schemas.xmlsoap.org/wsdl/soap/" '
        f'xmlns:tns="{NS}" xmlns:xsd="http://www.w3.org/2001/XMLSchema" '
        f'targetNamespace="{NS}">'
        '<wsdl:types><xsd:schema targetNamespace="' + NS + '">'
        + "".join(f'<xsd:element name="{name}"/>' for name in HANDLERS)
        + "</xsd:schema></wsdl:types>"
        + "".join(
            f'<wsdl:message name="{n}In"><wsdl:part name="parameters" element="tns:{n}"/></wsdl:message>'
            f'<wsdl:message name="{n}Out"><wsdl:part name="parameters" element="tns:{n}Response"/></wsdl:message>'
            for n in HANDLERS
        )
        + f'<wsdl:portType name="BankPortType">{operations}</wsdl:portType>'
        + '<wsdl:binding name="BankBinding" type="tns:BankPortType">'
        + '<soap:binding style="document" transport="http://schemas.xmlsoap.org/soap/http"/>'
        + "</wsdl:binding>"
        + '<wsdl:service name="BankService"><wsdl:port name="BankPort" binding="tns:BankBinding">'
        + '<soap:address location="http://localhost:8023/bank"/></wsdl:port></wsdl:service>'
        + "</wsdl:definitions>"
    )
    return Response(content=xml, media_type="text/xml; charset=utf-8")


@app.post("/bank")
async def call(
    request: Request,
    x_fault_mode: Optional[str] = Header(default=None),
) -> Response:
    raw = (await request.body()).decode("utf-8", errors="replace")

    if (x_fault_mode or "").lower() == "error500":
        return Response(content=_fault("ServiceUnavailable", "mock: банковский сервис недоступен"),
                        media_type="text/xml; charset=utf-8", status_code=500)

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        return Response(content=_fault("MalformedXML", f"XML не разобран: {error}"),
                        media_type="text/xml; charset=utf-8", status_code=400)

    header, body = None, None
    for child in root:
        name = _strip_ns(child.tag)
        if name == "Header":
            header = child
        elif name == "Body":
            body = child

    if body is None or len(body) == 0:
        return Response(content=_fault("EmptyBody", "Пустое SOAP Body"),
                        media_type="text/xml; charset=utf-8", status_code=400)

    try:
        _authenticate(header)
        operation_element = body[0]
        operation = _strip_ns(operation_element.tag)
        handler = HANDLERS.get(operation)
        if not handler:
            raise SoapFault("UnknownOperation", f"Операция '{operation}' не поддерживается")
        result = handler(operation_element)
    except SoapFault as fault:
        return Response(content=_fault(fault.code, fault.message),
                        media_type="text/xml; charset=utf-8", status_code=500)

    return Response(content=_envelope(result), media_type="text/xml; charset=utf-8")
