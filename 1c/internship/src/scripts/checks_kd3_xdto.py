#!/usr/bin/env python3
"""Проверки task_102: сообщение в духе EnterpriseData через XDTO-структуру.

Сообщение (Header: Sender/Recipient/Format; Body: объекты каталога)
разбирается приёмником по схеме: неизвестный тип объекта отклоняется,
загрузка между двумя «конфигурациями» дублей не создаёт.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_kd3_xdto.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

KNOWN_TYPES = {"Продукт"}


def build_message(products: list[dict], recipient: str) -> str:
    root = ET.Element("Message", {"xmlns": "http://rih.example/xdto/1"})
    ET.SubElement(root, "Header", {"Sender": "RIH", "Recipient": recipient,
                                   "Format": "EnterpriseData-RIH/1.0"})
    body = ET.SubElement(root, "Body")
    for p in products:
        ET.SubElement(body, "CatalogObject",
                      {"Type": "Продукт", "Артикул": p["sku"], "Наименование": p["name"]})
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def load_message(xml_text: str, receiver: dict[str, str]) -> dict:
    root = ET.fromstring(xml_text)
    for el in root.iter():  # пространство имён пакета — часть схемы, не семантика тега
        el.tag = el.tag.rsplit("}", 1)[-1]
    header = root.find("Header")
    assert header is not None and header.get("Format", "").startswith("EnterpriseData")
    result = {"created": 0, "updated": 0, "rejected": 0}
    for obj in root.iter("CatalogObject"):
        if obj.get("Type") not in KNOWN_TYPES:
            result["rejected"] += 1
            continue
        sku = obj.get("Артикул")
        if sku in receiver:
            result["updated"] += 1
        else:
            result["created"] += 1
        receiver[sku] = obj.get("Наименование")
    return result


def main() -> None:
    products = [{"sku": f"SKU-{i:05d}", "name": f"Товар {i}"} for i in range(1, 101)]
    message = build_message(products, "BRANCH")
    assert "EnterpriseData-RIH/1.0" in message and 'Recipient="BRANCH"' in message
    print("[ok] сообщение собрано: Header с получателем, Body — 100 объектов схемы")

    receiver: dict[str, str] = {}
    first = load_message(message, receiver)
    second = load_message(message, receiver)
    assert first == {"created": 100, "updated": 0, "rejected": 0}, first
    assert second == {"created": 0, "updated": 100, "rejected": 0}, second
    print("[ok] обмен между «конфигурациями»: повторная загрузка без дублей")

    bad = message.replace('Type="Продукт"', 'Type="НеизвестныйТип"', 1)
    result = load_message(bad, {})
    assert result["rejected"] == 1 and result["created"] == 99
    print("[ok] неизвестный тип объекта схемой отклонён, остальные приняты")


if __name__ == "__main__":
    main()
