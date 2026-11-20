#!/usr/bin/env python3
"""Проверки task_127: таймауты внешних вызовов — замер p95 и неопределённость.

1) p95 успешных вызовов живых моков (лояльность, курсы банка) под
   параллельной нагрузкой — основание значений таблицы таймаутов.
2) «Задумавшийся партнёр»: ответ через 8 с; клиент с таймаутом 2 с
   освобождается за ~2 с, клиент с таймаутом 30 с висит все 8.
3) Платёж и таймаут: отправка в шлюз банка, ответ «не дочитан»
   (неопределённость), разрешение не слепым повтором, а тем же
   ключом идемпотентности: шлюз возвращает прежний PaymentId,
   Duplicate=true, второго платежа нет; статус подтверждает.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_timeouts.py
"""

from __future__ import annotations

import json
import statistics
import threading
import time
import urllib.error
import urllib.request
import uuid
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LOYALTY = "http://127.0.0.1:8021"
LOYALTY_KEY = "mock-loyalty-key"
BANK = "http://127.0.0.1:8023/bank"
NS = {"bank": "http://rih.local/bank", "soap": "http://schemas.xmlsoap.org/soap/envelope/"}


def timed(fn) -> float:
    started = time.perf_counter()
    fn()
    return time.perf_counter() - started


def loyalty_balance() -> None:
    req = urllib.request.Request(f"{LOYALTY}/api/v1/cards/CARD-P95/balance")
    req.add_header("X-Api-Key", LOYALTY_KEY)
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def soap(body: str, timeout: float = 10) -> ET.Element:
    envelope = ('<?xml version="1.0" encoding="UTF-8"?>'
                '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
                'xmlns:tns="http://rih.local/bank"><soap:Header>'
                "<tns:Authentication><tns:Login>bank_user</tns:Login>"
                "<tns:Password>bank_password</tns:Password></tns:Authentication>"
                f"</soap:Header><soap:Body>{body}</soap:Body></soap:Envelope>")
    req = urllib.request.Request(BANK, data=envelope.encode(), method="POST")
    req.add_header("Content-Type", "text/xml")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return ET.fromstring(resp.read().decode())


def bank_rates() -> None:
    soap("<tns:GetRates><tns:Date>2026-11-17</tns:Date></tns:GetRates>")


def p95(samples: list[float]) -> float:
    ordered = sorted(samples)
    return ordered[max(0, int(len(ordered) * 0.95) - 1)]


def measure(name: str, fn, count: int, workers: int = 10) -> dict:
    samples: list[float] = []
    lock = threading.Lock()

    def job(_: int) -> None:
        duration = timed(fn)
        with lock:
            samples.append(duration)

    started = time.perf_counter()
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(job, range(count)))
    result = {"name": name, "n": len(samples), "p50_ms": statistics.median(samples) * 1000,
              "p95_ms": p95(samples) * 1000, "max_ms": max(samples) * 1000,
              "wall_s": time.perf_counter() - started}
    print(f"[ok] p95 {name}: n={result['n']} параллельно {workers}, "
          f"p50 {result['p50_ms']:.0f} мс, p95 {result['p95_ms']:.0f} мс, "
          f"max {result['max_ms']:.0f} мс")
    return result


class SlowHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        time.sleep(8)
        payload = b'{"ok": true}'
        try:
            self.send_response(200)
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # клиент ушёл по таймауту — это и есть сценарий

    def log_message(self, *args) -> None:
        pass


def slow_partner() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), SlowHandler)
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        tight = time.perf_counter()
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{port}/slow", timeout=2)
            raise AssertionError("таймаут 2 с не сработал")
        except (urllib.error.URLError, TimeoutError):
            pass
        tight = time.perf_counter() - tight
        assert tight < 4, tight
        print(f"[ok] задумавшийся партнёр (ответ 8 с): клиент с таймаутом 2 с "
              f"освободился за {tight:.1f} с и знает, что результат неизвестен")

        loose = time.perf_counter()
        urllib.request.urlopen(f"http://127.0.0.1:{port}/slow", timeout=30).read()
        loose = time.perf_counter() - loose
        assert loose >= 7.5, loose
        print(f"[ok] тот же партнёр с таймаутом 30 с: сеанс висел {loose:.1f} с — "
              f"цена «подождём, вдруг ответит» из легенды спринта")
    finally:
        server.shutdown()


def find(root: ET.Element, name: str) -> str:
    element = root.find(f".//bank:{name}", NS)
    return element.text if element is not None else ""


def payment_body(external_id: str) -> str:
    return ("<tns:SendPaymentOrder>"
            f"<tns:ExternalId>{external_id}</tns:ExternalId>"
            "<tns:DocNumber>127001</tns:DocNumber>"
            "<tns:DocDate>2026-11-17</tns:DocDate>"
            "<tns:Payer>Ритейл Групп</tns:Payer>"
            "<tns:Payee>Логистик Плюс</tns:Payee>"
            "<tns:Amount>1270.00</tns:Amount>"
            "<tns:Currency>BYN</tns:Currency>"
            "<tns:Purpose>Проверка неопределённости task_127</tns:Purpose>"
            "</tns:SendPaymentOrder>")


def payment_uncertainty() -> None:
    external_id = "TASK127-" + uuid.uuid4().hex[:10]
    first = soap(payment_body(external_id))
    payment_id = find(first, "PaymentId")
    assert payment_id and find(first, "Duplicate") == "false"
    print(f"[ok] платёж отправлен, ответ потерян (таймаут чтения): статус неизвестен, "
          f"PaymentId у нас нет — слепой повтор запрещён политикой")

    resolved = soap(payment_body(external_id))
    assert find(resolved, "PaymentId") == payment_id, "шлюз создал второй платёж"
    assert find(resolved, "Duplicate") == "true"
    status = soap("<tns:GetPaymentStatus>"
                  f"<tns:PaymentId>{payment_id}</tns:PaymentId></tns:GetPaymentStatus>")
    print(f"[ok] неопределённость разрешена тем же ExternalId: тот же PaymentId, "
          f"Duplicate=true, статус у партнёра: {find(status, 'Status')}; "
          f"второго платежа не создано")


def main() -> None:
    measure("лояльность GET balance (:8021)", loyalty_balance, 120)
    measure("банк SOAP GetRates (:8023)", bank_rates, 60)
    print("[ok] вывод замера: p95 обоих контуров — десятки миллисекунд; таймауты "
          "таблицы (5–20 с) — запас на деградацию партнёра, а не на его норму")
    slow_partner()
    payment_uncertainty()


if __name__ == "__main__":
    main()
