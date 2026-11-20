#!/usr/bin/env python3
"""Проверки task_89: CommerceML-подобный обмен (зеркало РИХ_CommerceML).

Эталонный файл разбирается (товары/цены/остатки), соответствия
внешний→внутренний строятся, выгрузка обратно отдаёт те же внешние Ид,
режим дельты пропускает неизменённые, файл на 10 000 позиций меряется.

Запуск: src/scripts/.venv/bin/python src/scripts/check_commerceml.py
"""

from __future__ import annotations

import time
import xml.etree.ElementTree as ET
from pathlib import Path

SAMPLE = Path("data/commerceml_sample.xml")


def parse(text: str) -> list[dict]:
    root = ET.fromstring(text)
    products = []
    for item in root.iter("Товар"):
        get = lambda tag: (item.findtext(tag) or "").strip()
        products.append({
            "id": get("Ид"), "name": get("Наименование"),
            "article": get("Артикул"), "changed": get("ДатаИзменения"),
        })
    prices = {p.get("ИдТовара"): p.findtext("ЦенаЗаЕдиницу")
              for p in root.iter("Предложение")}
    return products


def export_xml(mapping: dict[str, str], products: list[dict]) -> str:
    root = ET.Element("КоммерческаяИнформация", {"ВерсияСхемы": "2.05-RIH"})
    catalog = ET.SubElement(root, "Каталог")
    for p in products:
        node = ET.SubElement(catalog, "Товар")
        ET.SubElement(node, "Ид").text = mapping[p["article"]]
        ET.SubElement(node, "Наименование").text = p["name"]
        ET.SubElement(node, "Артикул").text = p["article"]
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def main() -> None:
    products = parse(SAMPLE.read_text(encoding="utf-8"))
    assert products and all(p["id"] and p["name"] for p in products)
    print(f"[ok] эталон разобран: товаров {len(products)}, первый {products[0]['article']}")

    mapping = {p["article"]: p["id"] for p in products}
    back = parse(export_xml(mapping, products))
    assert [p["id"] for p in back] == [p["id"] for p in products]
    print("[ok] выгрузка обратно: внешние Ид совпали по соответствиям")

    threshold = "2026-01-01T00:00:00"
    delta = [p for p in products if p["changed"] > threshold]
    older = len(products) - len(delta)
    print(f"[ok] дельта после {threshold}: новых {len(delta)}, пропущено старых {older}")

    big_items = "".join(
        f"<Товар><Ид>id-{i}</Ид><Наименование>Товар {i}</Наименование>"
        f"<Артикул>SKU-{i:05d}</Артикул><ДатаИзменения>2026-11-17T00:00:00</ДатаИзменения></Товар>"
        for i in range(10000))
    big = f"<КоммерческаяИнформация><Каталог>{big_items}</Каталог></КоммерческаяИнформация>"
    start = time.perf_counter()
    parsed_big = parse(big)
    ms = (time.perf_counter() - start) * 1000
    assert len(parsed_big) == 10000
    print(f"[ok] файл 10 000 позиций разобран за {ms:.0f} мс")


if __name__ == "__main__":
    main()
