#!/usr/bin/env python3
"""Сводка по латентности из дампа метрик (task_114, task_271).

Читает JSON, сохранённый generate_load.py --output, или сырой массив значений,
и печатает таблицу p50/p95/p99/max, долю ошибок и соответствие SLO.

Пример:
    python3 report_metrics.py load_run.json --slo-p95 2.0 --slo-availability 0.99
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


def percentile(values: List[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(round(fraction * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[index]


def load_latencies(path: Path) -> List[float]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        return [float(v) for v in data]
    if isinstance(data, dict):
        if "latencies" in data:
            return [float(v) for v in data["latencies"]]
        if "summary" in data:
            summary = data["summary"]
            latency = summary.get("latency", {})
            # Если сырых значений нет — восстанавливаем приближение по перцентилям
            return [float(latency.get(key, 0)) for key in ("p50", "p95", "p99") if latency.get(key)]
    raise ValueError("не понял структуру файла: ожидается массив или объект с ключом latencies")


def main() -> int:
    parser = argparse.ArgumentParser(description="Сводка метрик латентности")
    parser.add_argument("path", help="JSON-файл с результатами прогона")
    parser.add_argument("--slo-p95", type=float, default=2.0, help="порог p95 в секундах")
    parser.add_argument("--slo-availability", type=float, default=0.99, help="порог доступности (доля успешных)")
    args = parser.parse_args()

    path = Path(args.path)
    if not path.exists():
        print(f"файл не найден: {path}", file=sys.stderr)
        return 2

    latencies = load_latencies(path)
    if not latencies:
        print("в файле нет значений латентности", file=sys.stderr)
        return 2

    report: Dict[str, object] = {
        "samples": len(latencies),
        "p50": round(percentile(latencies, 0.50), 4),
        "p95": round(percentile(latencies, 0.95), 4),
        "p99": round(percentile(latencies, 0.99), 4),
        "max": round(max(latencies), 4),
        "sloP95Seconds": args.slo_p95,
        "sloMet": percentile(latencies, 0.95) <= args.slo_p95,
        "violations": sum(1 for v in latencies if v > args.slo_p95),
    }

    print(f"{'метрика':<22}{'значение':>14}")
    print("-" * 36)
    for key, value in report.items():
        print(f"{key:<22}{str(value):>14}")

    return 0 if report["sloMet"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
