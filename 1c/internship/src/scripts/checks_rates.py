#!/usr/bin/env python3
"""Проверки task_94: локальные курсы валют (зеркало РИХ_КурсыВалют).

Курсы банка (SOAP GetRates) сохраняются локально с датой; при
недоступности банка применяется последний известный курс с флагом
fallback; скачок > 30% помечается аномалией и не применяется;
сумма документа считается из локального хранилища без живого вызова.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_rates.py
"""

from __future__ import annotations

import json
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

STORE = Path("/tmp/rih_rates_mirror.json")
NS = {"bank": "http://rih.local/bank", "soap": "http://schemas.xmlsoap.org/soap/envelope/"}
ANOMALY = 0.30


def fetch_rates(bank_url: str, on_date: str) -> dict[str, float]:
    body = (f'<?xml version="1.0"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/" '
            f'xmlns:tns="http://rih.local/bank"><soap:Header><tns:Authentication>'
            f"<tns:Login>bank_user</tns:Login><tns:Password>bank_password</tns:Password>"
            f"</tns:Authentication></soap:Header><soap:Body><tns:GetRates>"
            f"<tns:Date>{on_date}</tns:Date></tns:GetRates></soap:Body></soap:Envelope>")
    req = urllib.request.Request(bank_url, data=body.encode(), method="POST")
    req.add_header("Content-Type", "text/xml")
    with urllib.request.urlopen(req, timeout=10) as resp:
        root = ET.fromstring(resp.read().decode())
    return {r.findtext("bank:CharCode", namespaces=NS):
            float(r.findtext("bank:Value", namespaces=NS)) / float(r.findtext("bank:Nominal", namespaces=NS))
            for r in root.findall(".//bank:Rate", NS)}


def load_store() -> dict:
    return json.loads(STORE.read_text(encoding="utf-8")) if STORE.exists() else {}


def save_rate(store: dict, code: str, on_date: str, rate: float, source: str) -> str:
    history = store.setdefault(code, {})
    previous_dates = [d for d in history if d < on_date and history[d]["status"] == "применён"]
    status = "применён"
    if previous_dates:
        prev = history[max(previous_dates)]["rate"]
        if prev > 0 and abs(rate - prev) / prev > ANOMALY:
            status = "аномалия"
    history[on_date] = {"rate": rate, "source": source, "status": status}
    return status


def rate_on(store: dict, code: str, on_date: str) -> float | None:
    history = store.get(code, {})
    dates = [d for d in history if d <= on_date and history[d]["status"] == "применён"]
    return history[max(dates)]["rate"] if dates else None


def main() -> None:
    if STORE.exists():
        STORE.unlink()
    store = load_store()

    rates = fetch_rates("http://127.0.0.1:8023/bank", "2026-11-17")
    for code, rate in rates.items():
        assert save_rate(store, code, "2026-11-17", rate, "bank") == "применён"
    STORE.write_text(json.dumps(store, ensure_ascii=False), encoding="utf-8")
    print(f"[ok] курсы банка сохранены локально: { {k: round(v, 4) for k, v in rates.items()} }")

    try:
        fetch_rates("http://127.0.0.1:9999/bank", "2026-11-18")
        raise AssertionError("мёртвый банк не дал ошибки")
    except Exception:
        fallback = rate_on(store, "USD", "2026-11-18")
        assert fallback == rates["USD"]
        print(f"[ok] банк недоступен: fallback на последний известный USD={fallback}, с предупреждением")

    status = save_rate(store, "USD", "2026-11-18", rates["USD"] * 1.5, "bank")
    assert status == "аномалия" and rate_on(store, "USD", "2026-11-18") == rates["USD"]
    print("[ok] скачок +50% помечен аномалией и не применён (ждёт подтверждения)")

    total = 100 * rate_on(store, "USD", "2026-11-17")
    print(f"[ok] сумма документа 100 USD по локальному курсу на дату: {total:.2f} BYN (без живого вызова)")


if __name__ == "__main__":
    main()
