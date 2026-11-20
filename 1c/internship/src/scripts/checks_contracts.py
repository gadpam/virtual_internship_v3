#!/usr/bin/env python3
"""Проверки task_140: контрактные тесты против OpenAPI в обе стороны.

Библиотека эталонов (tests/fixtures/contracts, 15 сообщений) гоняется
против схем docs/api/openapi.yaml: входящие — ожидания от партнёра,
исходящие — наши обещания партнёру. Эксперимент поломки контракта:
партнёр делает customer_ref обязательным — эталон «валидный вчера»
обязан упасть сегодня, до прода, а не ночью в обмене.
Финальный шаг — живая canary к mock_shop_api стенда.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_contracts.py
"""

from __future__ import annotations

import copy
import json
import urllib.request
from pathlib import Path

import yaml
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CANARY_URL = "http://127.0.0.1:8026"


def expand(node, components):
    if isinstance(node, dict):
        if "$ref" in node:
            name = node["$ref"].rsplit("/", 1)[-1]
            return expand(copy.deepcopy(components[name]), components)
        return {key: expand(value, components) for key, value in node.items()}
    if isinstance(node, list):
        return [expand(item, components) for item in node]
    return node


def load_schemas() -> dict:
    spec = yaml.safe_load((ROOT / "docs/api/openapi.yaml").read_text(encoding="utf-8"))
    components = spec["components"]["schemas"]
    return {name: expand(schema, components) for name, schema in components.items()}


def errors(schema: dict, payload) -> list:
    return list(Draft202012Validator(schema).iter_errors(payload))


def main(offline: bool = False) -> None:
    schemas = load_schemas()
    fixtures = ROOT / "tests/fixtures/contracts"
    manifest = json.loads((fixtures / "manifest.json").read_text(encoding="utf-8"))
    assert len(manifest["cases"]) >= 12
    for case in manifest["cases"]:
        payload = json.loads((fixtures / case["file"]).read_text(encoding="utf-8"))
        found = errors(schemas[case["schema"]], payload)
        if case["expect"] == "valid":
            assert not found, (case["file"], [e.message for e in found])
        else:
            assert found, (case["file"], "эталон обязан падать")
    print(f"[ok] библиотека эталонов: {len(manifest['cases'])} сообщений, "
          "входящие и исходящие соответствуют ожиданиям схемы")

    broken = copy.deepcopy(schemas["OrderIn"])
    broken["required"] = [*broken["required"], "customer_ref"]
    yesterdays = json.loads((fixtures / "01_order_valid_min.json").read_text(encoding="utf-8"))
    assert errors(broken, yesterdays), "сломанный контракт не пойман"
    assert not errors(schemas["OrderIn"], yesterdays)
    print("[ok] эксперимент: партнёр сделал customer_ref обязательным — "
          "вчерашний валидный эталон падает на новой схеме до прода")

    semantic = copy.deepcopy(schemas["OrderAccepted"])
    accepted = json.loads((fixtures / "13_order_accepted_valid.json").read_text(encoding="utf-8"))
    assert not errors(semantic, accepted)
    teleported = {**accepted, "status": "teleported"}
    assert errors(semantic, teleported)
    print("[ok] семантика контракта: статус вне enum ловится так же, как отсутствие поля")

    if offline:
        print("[ok] canary пропущена (--offline): в CI мока нет, "
              "живой шаг — стенд и расписание canary_check.py")
        return

    with urllib.request.urlopen(CANARY_URL + "/health", timeout=5) as response:
        health = json.loads(response.read())
    assert not errors(schemas["Health"], health), health
    request = urllib.request.Request(
        CANARY_URL + "/api/v1/products?limit=2",
        headers={"X-Api-Key": "mock-shop-key"})
    with urllib.request.urlopen(request, timeout=5) as response:
        page = json.loads(response.read())
    assert not errors(schemas["ProductList"], page)
    for item in page["items"]:
        assert not errors(schemas["Product"], item)
    print("[ok] canary: живой mock_shop_api отвечает по контракту (health + каталог)")


if __name__ == "__main__":
    import sys
    main(offline="--offline" in sys.argv)
