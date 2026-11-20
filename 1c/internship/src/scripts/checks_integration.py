#!/usr/bin/env python3
"""Проверки task_141: интеграционные тесты против живых mock.

Связка целиком HTTP → mock → ответ → обработка: каталог и заказы
магазина, лояльность, ТК, банк SOAP. Изоляция: каждый тест заводит
свои данные (уникальные идентификаторы прогона) и убирает за собой
(сторно лояльности, reset ТК); порядок запуска значения не имеет.
Негативы: 500 партнёра, таймаут, мусор вместо JSON, дубль.
Прогон повторяется 3 раза подряд: плавающий тест хуже отсутствующего.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_integration.py [прогонов]
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import uuid

SHOP = "http://127.0.0.1:8026"
LOYALTY = "http://127.0.0.1:8021"
TK = "http://127.0.0.1:8022"
BANK = "http://127.0.0.1:8023/bank"


def call(method: str, url: str, payload=None, headers=None, timeout=10.0):
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(
        url, data=body, method=method,
        headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as error:
        raw = error.read()
        try:
            return error.code, json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return error.code, {"raw": raw[:80]}


def soap(operation: str, inner: str) -> str:
    envelope = (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
        'xmlns:bank="http://rih.example/bank">'
        "<soap:Header><bank:Authentication>"
        "<bank:Login>bank_user</bank:Login>"
        "<bank:Password>bank_password</bank:Password>"
        "</bank:Authentication></soap:Header>"
        f"<soap:Body><bank:{operation}>{inner}</bank:{operation}>"
        "</soap:Body></soap:Envelope>")
    request = urllib.request.Request(
        BANK, data=envelope.encode(), method="POST",
        headers={"Content-Type": "text/xml; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.read().decode()


def field(xml: str, name: str) -> str:
    return xml.split(f"<bank:{name}>")[1].split("</")[0]


def suite(results: list[str]) -> None:
    # Уникальность на каждый прогон, а не на процесс: иначе второй
    # прогон ловит дубли первого и «плавает» на ровном месте.
    RUN = uuid.uuid4().hex[:8]  # noqa: N806
    shop_key = {"X-Api-Key": "mock-shop-key"}
    loyalty_key = {"X-Api-Key": "mock-loyalty-key"}
    tk_key = {"X-Api-Key": "mock-tk-key"}

    code, page = call("GET", SHOP + "/api/v1/products?limit=3", headers=shop_key)
    assert code == 200 and page["total"] >= 3 and len(page["items"]) == 3
    results.append("каталог магазина: страница и итоги")

    external = f"IT-{RUN}-order"
    order = {"external_id": external,
             "lines": [{"sku": "SKU-0001", "quantity": 2, "price": 50.0}]}
    idem = {**shop_key, "Idempotency-Key": f"IT-{RUN}-order-key"}
    code, created = call("POST", SHOP + "/api/v1/orders", order, idem)
    assert code in (200, 201), created
    code, again = call("POST", SHOP + "/api/v1/orders", order, idem)
    assert code in (200, 201) and again.get("duplicate") is True, again
    code, conflict = call("POST", SHOP + "/api/v1/orders", order, shop_key)
    assert code == 409, conflict
    results.append("заказ магазина: повтор с ключом — duplicate, без ключа — честный 409")

    card = f"IT-{RUN}-card"
    _, before = call("GET", f"{LOYALTY}/api/v1/cards/{card}/balance", headers=loyalty_key)
    op = {"operation_id": f"IT-{RUN}-accrue", "card": card, "points": 120}
    code, accrued = call("POST", LOYALTY + "/api/v1/accrue", op, loyalty_key)
    assert code == 200 and accrued["balance"] == before["balance"] + 120, accrued
    code, dup = call("POST", LOYALTY + "/api/v1/accrue", op, loyalty_key)
    assert dup.get("duplicate") is True
    _, after = call("GET", f"{LOYALTY}/api/v1/cards/{card}/balance", headers=loyalty_key)
    assert after["balance"] == before["balance"] + 120
    results.append("лояльность: начисление по дельте, дубль операции не двоит баллы")

    code, spent = call("POST", LOYALTY + "/api/v1/redeem",
                       {"operation_id": f"IT-{RUN}-redeem", "card": card, "points": 20},
                       loyalty_key)
    assert code == 200 and spent["balance"] == before["balance"] + 100
    call("POST", f"{LOYALTY}/api/v1/reverse?operation_id=IT-{RUN}-redeem",
         headers=loyalty_key)
    results.append("лояльность: списание и сторно-уборка за тестом")

    call("POST", TK + "/__reset__", headers=tk_key)
    code, calc = call("POST", TK + "/api/v1/calculate",
                      {"city_to": "Гомель", "weight_kg": 2.5, "volume_m3": 0.1}, tk_key)
    assert code == 200 and calc["price"] > 0, calc
    code, shipment = call("POST", TK + "/api/v1/shipments",
                          {"external_id": external, "city_to": "Гомель",
                           "weight_kg": 2.5}, tk_key)
    assert code == 201, shipment
    code, status = call("GET", f"{TK}/api/v1/shipments/{shipment['shipmentId']}", headers=tk_key)
    assert code == 200 and status["status"], status
    results.append("ТК: расчёт, заявка создана, статус читается")

    rates = soap("GetRates", "<bank:Date>2026-01-15</bank:Date>")
    assert "GetRatesResponse" in rates, rates[:200]
    results.append("банк: курсы по SOAP получены")

    ext = f"IT-{RUN}-pay"
    inner = (f"<bank:ExternalId>{ext}</bank:ExternalId>"
             "<bank:Amount>777.70</bank:Amount><bank:Currency>BYN</bank:Currency>")
    first = soap("SendPaymentOrder", inner)
    payment_id = field(first, "PaymentId")
    second = soap("SendPaymentOrder", inner)
    assert field(second, "PaymentId") == payment_id
    assert field(second, "Duplicate") == "true"
    status = soap("GetPaymentStatus", f"<bank:PaymentId>{payment_id}</bank:PaymentId>")
    assert field(status, "Status") in ("processing", "paid")
    results.append("банк: платёж идемпотентен по ExternalId, статус продвигается")

    code, _ = call("GET", SHOP + "/api/v1/products?fault=error500", headers=shop_key)
    assert code == 500
    results.append("негатив: 500 партнёра получен как 500, а не как тихий успех")

    started = time.time()
    try:
        call("GET", SHOP + "/api/v1/products?fault=delay:3000",
             headers=shop_key, timeout=1.0)
        raise SystemExit("таймаут не сработал")
    except Exception as exc:
        assert time.time() - started < 2.5, exc
    results.append("негатив: медленный партнёр отрезан клиентским таймаутом за ~1 с")

    code, garbage = call("GET", SHOP + "/api/v1/products?fault=garbage", headers=shop_key)
    assert code == 200 and "items" not in garbage, garbage
    results.append("негатив: мусор вместо каталога пойман проверкой формы ответа")

    op500 = {"operation_id": f"IT-{RUN}-flaky", "card": card, "points": 10}
    code, _ = call("POST", LOYALTY + "/api/v1/accrue?fault=error500", op500, loyalty_key)
    assert code == 500
    code, ok = call("POST", LOYALTY + "/api/v1/accrue", op500, loyalty_key)
    assert code == 200 and ok.get("duplicate") is not True
    _, final = call("GET", f"{LOYALTY}/api/v1/cards/{card}/balance", headers=loyalty_key)
    # 100 старт +120 начисление −20 списание +20 сторно +10 после 500 = +130
    assert final["balance"] == before["balance"] + 130, final
    results.append("негатив: после 500 повтор той же операцией начисляет ровно один раз")


def main() -> None:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    for run in range(1, runs + 1):
        results: list[str] = []
        started = time.time()
        suite(results)
        print(f"прогон {run}: {len(results)} тестов за {time.time() - started:.1f} с — зелёно")
    print("\n".join(f"[ok] {name}" for name in results))


if __name__ == "__main__":
    main()
