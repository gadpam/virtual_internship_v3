"""L2 · Контрактные тесты SOAP-сервиса банка (task_140).

SOAP-контракт проверяется иначе, чем REST: важен XML-конверт, пространства имён,
наличие SOAP Fault вместо HTTP-ошибки и структура ответа операции.
"""
import uuid
import xml.etree.ElementTree as ET

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.usefixtures("require_stand")]

SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
BANK_NS = "http://rih.local/bank"

ENVELOPE = """<soapenv:Envelope xmlns:soapenv="{soap}" xmlns:bank="{bank}">
  <soapenv:Header>
    <bank:Authentication><bank:Login>{login}</bank:Login><bank:Password>{password}</bank:Password></bank:Authentication>
  </soapenv:Header>
  <soapenv:Body>{body}</soapenv:Body>
</soapenv:Envelope>"""


def envelope(body: str, login: str = "bank_user", password: str = "bank_password") -> str:
    return ENVELOPE.format(soap=SOAP_NS, bank=BANK_NS, login=login, password=password, body=body)


def post_soap(client, bank, payload: str):
    return client.post(f"{bank.base}/bank", content=payload.encode("utf-8"),
                       headers={"Content-Type": "text/xml; charset=utf-8"})


def parse(response) -> ET.Element:
    assert response.headers["content-type"].startswith("text/xml"), response.headers
    return ET.fromstring(response.text)


def test_wsdl_is_available_and_lists_operations(client, bank):
    response = client.get(f"{bank.base}/bank?wsdl")
    assert response.status_code == 200
    for operation in ("GetStatement", "SendPaymentOrder", "GetPaymentStatus", "GetRates"):
        assert operation in response.text


def test_missing_credentials_returns_soap_fault(client, bank):
    response = post_soap(client, bank, envelope("<bank:GetRates><bank:Date>2026-01-15</bank:Date></bank:GetRates>",
                                                login="nobody", password="wrong"))
    assert response.status_code == 500
    root = parse(response)
    fault = root.find(f"{{{SOAP_NS}}}Body/{{{SOAP_NS}}}Fault")
    assert fault is not None
    assert "AuthFailed" in (fault.findtext("faultcode") or "")


def test_malformed_xml_returns_fault_not_html(client, bank):
    response = post_soap(client, bank, "<soapenv:Envelope><unclosed>")
    assert response.status_code == 400
    assert response.text.lstrip().startswith("<?xml") or response.text.lstrip().startswith("<")
    assert "<html" not in response.text.lower()


def test_get_rates_returns_rate_structure(client, bank):
    response = post_soap(client, bank, envelope("<bank:GetRates><bank:Date>2026-01-15</bank:Date></bank:GetRates>"))
    assert response.status_code == 200
    root = parse(response)
    rates = root.findall(f".//{{{BANK_NS}}}Rate")
    assert rates, "операция GetRates вернула пустой список курсов"

    codes = {rate.findtext(f"{{{BANK_NS}}}CharCode") for rate in rates}
    assert {"USD", "EUR", "RUB"}.issubset(codes)
    for rate in rates:
        assert rate.findtext(f"{{{BANK_NS}}}Date") == "2026-01-15"
        value = float(rate.findtext(f"{{{BANK_NS}}}Value"))
        nominal = int(rate.findtext(f"{{{BANK_NS}}}Nominal"))
        assert value > 0 and nominal > 0


def test_get_statement_rejects_inverted_period(client, bank):
    body = ("<bank:GetStatement><bank:DateFrom>2026-03-01</bank:DateFrom>"
            "<bank:DateTo>2026-01-01</bank:DateTo></bank:GetStatement>")
    response = post_soap(client, bank, envelope(body))
    assert response.status_code == 500
    root = parse(response)
    assert "InvalidPeriod" in ET.tostring(root, encoding="unicode")


def test_send_payment_order_is_idempotent_by_external_id(client, bank):
    external_id = f"PAY-{uuid.uuid4().hex[:12]}"
    body = (f"<bank:SendPaymentOrder><bank:ExternalId>{external_id}</bank:ExternalId>"
            "<bank:DocNumber>0000123</bank:DocNumber><bank:DocDate>2026-02-10</bank:DocDate>"
            "<bank:Amount>1250.50</bank:Amount><bank:Currency>BYN</bank:Currency>"
            "<bank:Purpose>Оплата по счёту</bank:Purpose></bank:SendPaymentOrder>")

    first = parse(post_soap(client, bank, envelope(body)))
    second = parse(post_soap(client, bank, envelope(body)))

    first_id = first.findtext(f".//{{{BANK_NS}}}PaymentId")
    second_id = second.findtext(f".//{{{BANK_NS}}}PaymentId")
    assert first_id and first_id == second_id
    assert second.findtext(f".//{{{BANK_NS}}}Duplicate") == "true"


def test_negative_amount_is_fault(client, bank):
    body = ("<bank:SendPaymentOrder><bank:ExternalId>PAY-NEG</bank:ExternalId>"
            "<bank:Amount>-10</bank:Amount></bank:SendPaymentOrder>")
    response = post_soap(client, bank, envelope(body))
    assert response.status_code == 500
    assert "InvalidAmount" in response.text


def test_unknown_operation_is_fault(client, bank):
    response = post_soap(client, bank, envelope("<bank:MakeCoffee/>"))
    assert response.status_code == 500
    assert "UnknownOperation" in response.text


def test_fault_mode_returns_service_unavailable(client, bank):
    response = client.post(f"{bank.base}/bank",
                           content=envelope("<bank:GetRates><bank:Date>2026-01-15</bank:Date></bank:GetRates>").encode(),
                           headers={"Content-Type": "text/xml; charset=utf-8", "X-Fault-Mode": "error500"})
    assert response.status_code == 500
    assert "ServiceUnavailable" in response.text
