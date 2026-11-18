"""L4 · Снятие профиля нагрузки (task_143, task_201).

Тесты медленные и по умолчанию помечены `load`: запуск `pytest -q -m load`.
Проверяем не «выдержит ли сервер», а форму профиля: латентность растёт плавно,
ошибки появляются только на пике, после пика система возвращается к базовому уровню.
"""
import asyncio
import statistics
import time

import pytest

pytestmark = [pytest.mark.load, pytest.mark.slow, pytest.mark.usefixtures("require_stand")]


def percentile(values, fraction):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(int(round(fraction * (len(ordered) - 1))), len(ordered) - 1)]


async def drive(url, headers, rps, duration, timeout=10.0):
    """Отправляет запросы с заданным RPS и возвращает (латентности, коды ответов).

    Клиент создаётся внутри корутины: один прогон — один event loop. Переиспользовать
    httpx.AsyncClient между разными asyncio.run нельзя — пул соединений привязан к циклу.
    """
    httpx = pytest.importorskip("httpx", reason="нужен httpx: pip install -r requirements.txt")
    latencies, codes, interval = [], {}, 1.0 / rps if rps > 0 else 0
    deadline = time.perf_counter() + duration
    async with httpx.AsyncClient() as client:
        while time.perf_counter() < deadline:
            started = time.perf_counter()
            try:
                response = await client.get(url, headers=headers, params={"limit": 5}, timeout=timeout)
                latencies.append(time.perf_counter() - started)
                codes[response.status_code] = codes.get(response.status_code, 0) + 1
            except Exception:  # noqa: BLE001 - сетевая ошибка тоже результат прогона
                latencies.append(time.perf_counter() - started)
                codes[-1] = codes.get(-1, 0) + 1
            remaining = interval - (time.perf_counter() - started)
            if remaining > 0:
                await asyncio.sleep(remaining)
    return latencies, codes


def test_baseline_profile_is_stable(shop):
    latencies, codes = asyncio.run(
        drive(f"{shop.base}/api/v1/products", {"X-Api-Key": shop.api_key}, rps=5, duration=20))
    assert latencies, "не выполнено ни одного запроса"
    assert codes.get(200, 0) / len(latencies) > 0.95
    assert percentile(latencies, 0.95) < 2.0, f"p95 базовой нагрузки превысил SLO: {percentile(latencies, 0.95):.3f}"


def test_latency_grows_sublinearly_under_target_load(shop):
    headers = {"X-Api-Key": shop.api_key}
    url = f"{shop.base}/api/v1/products"
    low = asyncio.run(drive(url, headers, rps=5, duration=15))[0]
    high = asyncio.run(drive(url, headers, rps=20, duration=15))[0]

    p95_low, p95_high = percentile(low, 0.95), percentile(high, 0.95)
    assert p95_high < p95_low * 5, (
        f"латентность растёт нелинейно: p95 {p95_low:.3f} → {p95_high:.3f} при росте нагрузки в 4 раза. "
        "Это и есть точка, с которой начинается деградация (task_201)."
    )


def test_rate_limited_partner_returns_429_without_cascading_errors(tk):
    """ТК ограничивает 10 запросов в минуту: клиент обязан получить 429, а не таймауты."""

    async def run():
        httpx = pytest.importorskip("httpx", reason="нужен httpx: pip install -r requirements.txt")
        headers = {"X-Api-Key": tk.api_key, "Content-Type": "application/json"}
        body = {"city_to": "Минск", "weight_kg": 1.0, "volume_m3": 0.01}
        codes = {}
        async with httpx.AsyncClient() as session:
            for _ in range(25):
                response = await session.post(f"{tk.base}/api/v1/calculate", headers=headers,
                                              json=body, timeout=10.0)
                codes[response.status_code] = codes.get(response.status_code, 0) + 1
        return codes

    codes = asyncio.run(run())
    assert codes.get(429, 0) > 0, f"лимит частоты не сработал: {codes}"
    assert codes.get(200, 0) > 0
    assert -1 not in codes, "появились сетевые ошибки — клиент не справляется с лимитом"


def test_recovery_after_peak(shop):
    headers = {"X-Api-Key": shop.api_key}
    url = f"{shop.base}/api/v1/products"
    peak = asyncio.run(drive(url, headers, rps=50, duration=20))[0]
    time.sleep(5)  # пауза на стабилизацию пула соединений и кеша
    after = asyncio.run(drive(url, headers, rps=5, duration=15))[0]

    p95_peak, p95_after = percentile(peak, 0.95), percentile(after, 0.95)
    assert p95_after < p95_peak * 1.5, (
        f"после пика p95 не вернулся к базовому уровню: {p95_peak:.3f} → {p95_after:.3f}"
    )
    assert statistics.median(after) < 1.0
