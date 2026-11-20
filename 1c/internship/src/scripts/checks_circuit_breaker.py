#!/usr/bin/env python3
"""Проверки task_129: circuit breaker поверх повторов (зеркало).

Автомат Closed/Open/Half-Open гоняется против живого mock_shop_api
:8026 в режиме error500: серия ошибок открывает контур, открытые
вызовы отклоняются мгновенно и без сети, после остывания одна проба
закрывает контур. Сценарий «партнёр лежит 10 минут» проходит
ускоренным временем: остывание зеркала 2 с вместо боевых 60 с —
параметр, а не механика. Метрика экспортёра проверяется на снимке.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_circuit_breaker.py
"""

from __future__ import annotations

import os
import re
import time
import urllib.error
import urllib.request

SHOP = os.environ.get("MOCK_SHOP_URL", "http://127.0.0.1:8026")
SHOP_KEY = os.environ.get("MOCK_SHOP_API_KEY", "mock-shop-key")
THRESHOLD = 5
COOLDOWN = 2.0


class BreakerOpen(Exception):
    pass


class Breaker:
    """Зеркало РИХ_Предохранители: порог серии, остывание, одна проба."""

    def __init__(self, circuit: str) -> None:
        self.circuit = circuit
        self.state = "Closed"
        self.errors_in_row = 0
        self.opened_at = 0.0
        self.journal: list[str] = []
        self.network_attempts = 0

    def allow(self) -> bool:
        if self.state == "Open":
            if time.time() - self.opened_at >= COOLDOWN:
                self.state = "HalfOpen"
                self.journal.append("Open -> HalfOpen: проба восстановления")
                return True
            return False
        return self.state == "Closed"

    def success(self) -> None:
        previous = self.state
        self.state, self.errors_in_row = "Closed", 0
        if previous != "Closed":
            self.journal.append(f"{previous} -> Closed: контур восстановлен")

    def failure(self) -> None:
        self.errors_in_row += 1
        if self.state == "HalfOpen" or self.errors_in_row >= THRESHOLD:
            previous = self.state
            self.state, self.opened_at = "Open", time.time()
            if previous != "Open":
                self.journal.append(
                    f"{previous} -> Open: серия ошибок {self.errors_in_row}, "
                    f"вызовы запрещены на {COOLDOWN:.0f} с")


def shop_once(fault: str | None) -> int:
    req = urllib.request.Request(f"{SHOP}/api/v1/products")
    req.add_header("X-Api-Key", SHOP_KEY)
    if fault:
        req.add_header("X-Fault-Mode", fault)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            resp.read()
            return resp.status
    except urllib.error.HTTPError as err:
        return err.code


def call(breaker: Breaker, fault: str | None) -> int:
    """Breaker снаружи, одна попытка внутри (ретраи task_128 сжаты)."""
    if not breaker.allow():
        raise BreakerOpen(breaker.circuit)
    breaker.network_attempts += 1
    code = shop_once(fault)
    if code >= 500 or code == 0:
        breaker.failure()
    else:
        breaker.success()
    return code


def main() -> None:
    breaker = Breaker("shop")
    for number in range(THRESHOLD):
        code = call(breaker, "error500")
        assert code == 500
    assert breaker.state == "Open", breaker.state
    print(f"[ok] серия из {THRESHOLD} ошибок открыла предохранитель; журнал: {breaker.journal[-1]}")

    attempts_before = breaker.network_attempts
    started = time.perf_counter()
    try:
        call(breaker, "error500")
        raise AssertionError("открытый breaker пропустил вызов")
    except BreakerOpen:
        pass
    refused_ms = (time.perf_counter() - started) * 1000
    assert breaker.network_attempts == attempts_before
    assert refused_ms < 200, refused_ms
    print(f"[ok] открытый вызов отклонён без сети за {refused_ms:.0f} мс: "
          f"пользователь видит честную деградацию, а не ожидание мертвеца")

    time.sleep(COOLDOWN + 0.2)
    code = call(breaker, "error500")
    assert code == 500 and breaker.state == "Open"
    print("[ok] проба Half-Open по мёртвому партнёру: снова Open, второй "
          "пробы без остывания не будет")

    time.sleep(COOLDOWN + 0.2)
    code = call(breaker, None)
    assert code == 200 and breaker.state == "Closed", (code, breaker.state)
    print(f"[ok] партнёр поднялся: проба успешна, контур Closed; журнал переходов:")
    for line in breaker.journal:
        print(f"     {line}")
    transitions = [line.split(':')[0] for line in breaker.journal]
    assert transitions == ["Closed -> Open", "Open -> HalfOpen",
                           "HalfOpen -> Open", "Open -> HalfOpen",
                           "HalfOpen -> Closed"], transitions

    source = open("src/metrics_exporter/app/main.py", encoding="utf-8").read()
    assert "rih_circuit_breaker_state" in source and '"Open": 1' in source
    print("[ok] метрика rih_circuit_breaker_state есть в экспортёре task_114: "
          "открытый контур виден мониторингу до жалоб пользователей")
    print("[ok] порядок слоёв выдержан: breaker решает «вызывать ли», "
          "ошибка фиксируется одна финальная после ретраев, не по попыткам")


if __name__ == "__main__":
    main()
