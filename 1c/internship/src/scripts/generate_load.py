#!/usr/bin/env python3
"""Генератор нагрузки для учебного стенда RIH (task_143, task_200, task_201).

Отправляет запросы к целевому URL с заданным RPS, измеряет латентность и печатает
сводку p50/p95/p99 и долю ошибок. Специально простой: цель — научиться читать
профиль нагрузки, а не заменить JMeter.

Пример:
    python3 generate_load.py --url http://localhost:8020/api/v1/orders \
        --header "X-Api-Key:mock-shop-key" --rps 20 --duration 60
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from typing import Dict, List

try:
    import httpx
except ImportError:  # pragma: no cover
    print("Нужен httpx: pip install -r requirements.txt", file=sys.stderr)
    raise SystemExit(2)


def parse_header(raw: str) -> tuple:
    if ":" not in raw:
        raise argparse.ArgumentTypeError(f"заголовок должен быть в виде Key:Value, получено {raw!r}")
    key, value = raw.split(":", 1)
    return key.strip(), value.strip()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Генератор нагрузки")
    parser.add_argument("--url", required=True, help="целевой URL")
    parser.add_argument("--method", default="GET", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    parser.add_argument("--header", action="append", type=parse_header, default=[], metavar="Key:Value")
    parser.add_argument("--body", default=None, help="JSON-тело запроса")
    parser.add_argument("--rps", type=float, default=5.0, help="запросов в секунду")
    parser.add_argument("--duration", type=float, default=30.0, help="длительность прогона, секунд")
    parser.add_argument("--timeout", type=float, default=10.0, help="таймаут запроса, секунд")
    parser.add_argument("--output", default=None, help="файл JSON с сырыми результатами")
    parser.add_argument("--expect", default=None, help="требуемый код ответа (например 200)")
    return parser


async def worker(client: httpx.AsyncClient, args: argparse.Namespace, headers: Dict[str, str],
                 latencies: List[float], codes: Dict[int, int], failures: List[str]) -> None:
    interval = 1.0 / args.rps if args.rps > 0 else 0.0
    deadline = time.perf_counter() + args.duration
    while time.perf_counter() < deadline:
        started = time.perf_counter()
        try:
            response = await client.request(args.method, args.url, headers=headers,
                                            content=args.body, timeout=args.timeout)
            elapsed = time.perf_counter() - started
            latencies.append(elapsed)
            codes[response.status_code] = codes.get(response.status_code, 0) + 1
            if args.expect and response.status_code != int(args.expect):
                failures.append(f"{response.status_code}: {response.text[:120]}")
        except Exception as error:  # noqa: BLE001 — фиксируем любую сетевую ошибку
            latencies.append(time.perf_counter() - started)
            codes[-1] = codes.get(-1, 0) + 1
            failures.append(f"{type(error).__name__}: {error}")
        remaining = interval - (time.perf_counter() - started)
        if remaining > 0:
            await asyncio.sleep(remaining)


def percentile(values: List[float], fraction: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    index = min(int(round(fraction * (len(ordered) - 1))), len(ordered) - 1)
    return ordered[index]


def main() -> int:
    args = build_parser().parse_args()
    headers = dict(args.header)
    latencies: List[float] = []
    codes: Dict[int, int] = {}
    failures: List[str] = []

    workers = max(1, int(args.rps / 5) or 1)
    started = time.perf_counter()

    async def run() -> None:
        async with httpx.AsyncClient() as client:
            await asyncio.gather(*(worker(client, args, headers, latencies, codes, failures)
                                   for _ in range(workers)))

    asyncio.run(run())
    wall = time.perf_counter() - started

    total = len(latencies)
    summary = {
        "url": args.url,
        "method": args.method,
        "plannedRps": args.rps,
        "durationSeconds": round(wall, 2),
        "requests": total,
        "actualRps": round(total / wall, 2) if wall > 0 else 0,
        "statusCodes": codes,
        "latency": {
            "p50": round(percentile(latencies, 0.50), 4),
            "p95": round(percentile(latencies, 0.95), 4),
            "p99": round(percentile(latencies, 0.99), 4),
            "max": round(max(latencies), 4) if latencies else 0,
            "avg": round(statistics.fmean(latencies), 4) if latencies else 0,
        },
        "failuresSample": failures[:20],
        "failureCount": len(failures),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump({"summary": summary, "latencies": latencies}, handle, ensure_ascii=False)
        print(f"сырые данные: {args.output}", file=sys.stderr)

    return 1 if failures and args.expect else 0


if __name__ == "__main__":
    raise SystemExit(main())
