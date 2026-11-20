#!/usr/bin/env python3
"""Проверки task_114: метрики интеграций и алерт-правила (зеркало).

Метрики считаются из журнала вызовов: по сервисам, доля ошибок,
средняя и p95 задержки, размер очереди, давность успеха.
Три алерта проверяются на искусственных сбоях; снимок проходит
через настоящий код экспортёра Prometheus стенда.

Запуск: /tmp/walk-venv/bin/python src/scripts/checks_metrics.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path("src/metrics_exporter")))


def percentile(samples: list[float], p: float) -> float:
    ordered = sorted(samples)
    return ordered[max(int(len(ordered) * p) - 1, 0)]


def compute(rows: list[dict], queue_size: int, minutes_since_success: float) -> dict:
    by_system: dict[str, list[dict]] = {}
    for row in rows:
        by_system.setdefault(row["system"], []).append(row)
    metrics = {}
    for system, items in by_system.items():
        samples = [i["ms"] for i in items]
        errors = sum(1 for i in items if i["status"] >= 400)
        metrics[system] = {
            "requests_total": len(items),
            "error_share": round(errors / len(items) * 100, 1) if items else 0.0,
            "latency_avg_ms": round(sum(samples) / len(samples), 1),
            "latency_p95_ms": percentile(samples, 0.95),
        }
    metrics["queue"] = {"queue_size": queue_size,
                        "last_success_age_min": minutes_since_success}
    return metrics


def alerts(metrics: dict) -> list[str]:
    fired = []
    if metrics["queue"]["queue_size"] > 1000:
        fired.append("очередь > 1000")
    for system, values in metrics.items():
        if system != "queue" and values["requests_total"] >= 20 \
                and values["error_share"] > 5:
            fired.append(f"доля ошибок {system} > 5%")
    if metrics["queue"]["last_success_age_min"] > 60:
        fired.append("нет успешных обменов больше часа")
    return fired


def main() -> None:
    rows = [{"system": "shop", "status": 200, "ms": 10 + i} for i in range(96)]
    rows += [{"system": "shop", "status": 500, "ms": 900} for _ in range(4)]
    rows += [{"system": "tk", "status": 200, "ms": 50} for _ in range(10)]
    metrics = compute(rows, queue_size=1200, minutes_since_success=75)
    assert metrics["shop"]["requests_total"] == 100
    assert metrics["shop"]["error_share"] == 4.0
    assert metrics["shop"]["latency_p95_ms"] >= 90
    print(f"[ok] метрики: shop {metrics['shop']}, очередь {metrics['queue']}")

    fired = alerts(metrics)
    assert "очередь > 1000" in fired and "нет успешных обменов больше часа" in fired
    assert not any("shop" in f for f in fired), "4% ошибок не должны алертить при пороге 5%"
    print(f"[ok] алерты на искусственном сбое: {fired}")

    rows2 = [{"system": "loyalty", "status": 500, "ms": 100} for _ in range(10)]
    rows2 += [{"system": "loyalty", "status": 200, "ms": 20} for _ in range(90)]
    fired2 = alerts(compute(rows2, queue_size=3, minutes_since_success=5))
    assert any("loyalty" in f for f in fired2)
    print(f"[ok] доля ошибок 10% у loyalty ловится: {fired2}")

    from app.main import build_text  # настоящий экспортёр стенда
    payload = {"integrationRequests": [
                   {"system": "shop", "operation": "orders", "status": "200", "count": 96}],
               "durations": [{"system": "shop", "operation": "orders",
                              "samples": [10, 20, 30]}],
               "queueSize": 3}
    text = build_text(payload, True)
    assert "rih_integration_requests_total" in text and 'system="shop"' in text
    print("[ok] снимок проходит через экспортёр: Prometheus-текст с метками сервисов")


if __name__ == "__main__":
    main()
