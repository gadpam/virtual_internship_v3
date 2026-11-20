#!/usr/bin/env python3
"""Первый учебный скрипт стажёра (task_5): CSV -> JSON-сводка + HTTP-проверка.

Что делает:
  1) читает план продаж из CSV (разделитель ';', колонка planned_quantity)
     и пишет сводку в JSON-файл;
  2) делает HTTP-запрос к учебному сервису (GET /health) стандартным urllib
     и фиксирует статус, заголовок и начало тела ответа;
  3) умеет демонстрировать обработку ошибок: нет файла, битый JSON настроек,
     HTTP 500 от mock-сервиса в fault-режиме. Каждая ошибка превращается
     в понятное сообщение человеку и ненулевой код возврата.

Запуск (из каталога 1c/internship):
  src/scripts/.venv/bin/python src/scripts/first_python_check.py
  src/scripts/.venv/bin/python src/scripts/first_python_check.py --check-errors
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import urllib.error
import urllib.request
from decimal import Decimal, InvalidOperation
from pathlib import Path

DEFAULT_API_KEY = "mock-shop-key"  # MOCK_SHOP_API_KEY из tools/.env.example


class CheckError(Exception):
    """Ошибка, которую скрипт обязан показать человеку, а не проглотить."""


def summarize_csv(csv_path: Path) -> dict:
    """Считает строки и итоги плана продаж. Колонки берём по имени."""
    if not csv_path.exists():
        raise CheckError(f"файл не найден: {csv_path}")
    total_rows = 0
    total_quantity = 0
    total_amount = Decimal("0")
    stores: set[str] = set()
    with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=";")
        if reader.fieldnames is None or "planned_quantity" not in reader.fieldnames:
            raise CheckError(
                f"в {csv_path.name} нет колонки planned_quantity; "
                f"заголовки: {reader.fieldnames}"
            )
        for line_number, row in enumerate(reader, start=2):
            try:
                quantity = int(row["planned_quantity"])
                amount = Decimal(row.get("planned_amount") or "0")
            except (ValueError, InvalidOperation) as exc:
                raise CheckError(
                    f"строка {line_number}: не число в planned_quantity/"
                    f"planned_amount: {row!r}"
                ) from exc
            total_rows += 1
            total_quantity += quantity
            total_amount += amount
            stores.add(row.get("store_code", ""))
    return {
        "source_file": csv_path.name,
        "rows": total_rows,
        "stores": len(stores),
        "total_planned_quantity": total_quantity,
        "total_planned_amount": str(total_amount),
    }


def load_settings(settings_path: Path) -> dict:
    """Читает необязательный JSON настроек; битый JSON — отдельная ошибка."""
    if not settings_path.exists():
        raise CheckError(f"файл настроек не найден: {settings_path}")
    try:
        return json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CheckError(f"битый JSON в {settings_path.name}: {exc}") from exc


def http_get(url: str, api_key: str | None = None) -> tuple[int, str, str]:
    """GET стандартным urllib. Возвращает (статус, Content-Type, тело)."""
    request = urllib.request.Request(url)
    if api_key:
        request.add_header("X-Api-Key", api_key)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return response.status, response.headers.get("Content-Type", ""), body
    except urllib.error.HTTPError as exc:
        raise CheckError(
            f"HTTP {exc.code} от {url}: {exc.read().decode('utf-8', 'replace')[:200]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise CheckError(f"сервис недоступен ({url}): {exc.reason}") from exc


def run_error_checks(base_url: str) -> None:
    """Демонстрирует три обрабатываемые ошибки; каждая обязана случиться."""
    checks = [
        ("нет файла", lambda: summarize_csv(Path("data/no_such_file.csv"))),
        (
            "битый JSON",
            lambda: load_settings(_write_broken_json()),
        ),
        (
            "HTTP 500 (fault)",
            lambda: http_get(
                f"{base_url}/api/v1/products?fault=error500", api_key=DEFAULT_API_KEY
            ),
        ),
    ]
    for name, action in checks:
        try:
            action()
        except CheckError as exc:
            print(f"[ok] ошибка «{name}» обработана: {exc}")
        else:
            raise CheckError(f"проверка «{name}» не воспроизвела ошибку")


def _write_broken_json() -> Path:
    broken = Path(__file__).with_name("_broken_settings.json")
    broken.write_text('{"health_url": "http://localhost:8020/health", ', encoding="utf-8")
    return broken


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/sales_plan_sample.csv"),
        help="план продаж (разделитель ';')",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("src/scripts/first_python_check_summary.json"),
        help="куда писать JSON-сводку",
    )
    parser.add_argument(
        "--base-url", default="http://localhost:8020", help="базовый URL mock_shop_api"
    )
    parser.add_argument(
        "--settings", type=Path, help="необязательный JSON настроек (health_url)"
    )
    parser.add_argument(
        "--check-errors", action="store_true", help="прогнать демонстрацию ошибок"
    )
    args = parser.parse_args()

    try:
        health_url = f"{args.base_url}/health"
        if args.settings:
            health_url = load_settings(args.settings).get("health_url", health_url)

        summary = summarize_csv(args.csv)
        status, content_type, body = http_get(health_url)
        summary["health"] = {
            "url": health_url,
            "status": status,
            "content_type": content_type,
            "body_prefix": body[:120],
        }
        args.out.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"сводка записана: {args.out}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))

        if args.check_errors:
            run_error_checks(args.base_url)
    except CheckError as exc:
        print(f"ОШИБКА: {exc}", file=sys.stderr)
        return 1
    finally:
        _write_broken_json().unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
