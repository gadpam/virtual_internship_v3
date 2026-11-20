#!/usr/bin/env python3
"""Проверки task_75: JSON/XML туда-обратно (зеркало РИХ_Форматы).

Кейсы: плоская структура, вложенность, массив, Null, дата ISO 8601,
спецсимволы, пустые значения, числа с копейками, сравнение размеров
одного документа в JSON и XML.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_formats.py
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET


def to_xml(data: dict, root: str = "Документ") -> str:
    def build(name: str, value) -> ET.Element:
        el = ET.Element(name)
        if isinstance(value, dict):
            for k, v in value.items():
                el.append(build(k, v))
        elif isinstance(value, list):
            for item in value:
                el.append(build("Item", item))
        elif value is not None:
            el.text = str(value)
        return el

    return ET.tostring(build(root, data), encoding="unicode", xml_declaration=True)


def from_xml(text: str):
    def parse(el: ET.Element):
        kids = list(el)
        if not kids:
            return el.text or ""
        out: dict = {}
        for kid in kids:
            value = parse(kid)
            if kid.tag in out:
                if not isinstance(out[kid.tag], list):
                    out[kid.tag] = [out[kid.tag]]
                out[kid.tag].append(value)
            else:
                out[kid.tag] = value
        if "Item" in out and len(out) == 1:
            return out["Item"]
        return out

    return parse(ET.fromstring(text))


def check(name: str, cond: bool) -> None:
    assert cond, name
    print(f"[ok] {name}")


def main() -> None:
    doc = {
        "Номер": "П-001",
        "Дата": "2026-01-31T21:00:00Z",
        "Склад": "РЦ-Минск",
        "Комментарий": None,
        "Товары": [
            {"Номенклатура": "Молоко «Домик» & Co", "Количество": 15, "Цена": 2.5},
            {"Номенклатура": "Хлеб", "Количество": 10, "Цена": 1.2},
        ],
        "Итого": 49.5,
    }

    js = json.dumps(doc, ensure_ascii=False)
    back = json.loads(js)
    check("JSON туда-обратно равен исходному", back == doc)
    check("JSON: Null сохранён", back["Комментарий"] is None)
    check("JSON: вложенный массив", back["Товары"][1]["Номенклатура"] == "Хлеб")
    check("JSON: спецсимволы не сломали разбора", "«Домик» & Co" in back["Товары"][0]["Номенклатура"])
    check("JSON: дата ISO строкой как в контракте", back["Дата"] == "2026-01-31T21:00:00Z")

    flat = {"А": "1", "Б": {"В": "x"}, "Список": ["a", "b"]}
    xml_text = to_xml(flat)
    restored = from_xml(xml_text)
    check("XML туда-обратно: вложенность", restored["Б"]["В"] == "x")
    check("XML туда-обратно: массив из Item", restored["Список"] == ["a", "b"])

    xml_doc = to_xml(doc)
    restored_doc = from_xml(xml_doc)
    check("XML: строки документа на месте", restored_doc["Товары"][0]["Количество"] == "15")
    check("XML: пустой комментарий не упал", "Комментарий" in restored_doc)

    json_size = len(js.encode("utf-8"))
    xml_size = len(xml_doc.encode("utf-8"))
    print(f"[ok] размер поступления: JSON {json_size} байт, XML {xml_size} байт "
          f"(XML больше на {round((xml_size / json_size - 1) * 100)}%)")
    assert xml_size > json_size


if __name__ == "__main__":
    main()
