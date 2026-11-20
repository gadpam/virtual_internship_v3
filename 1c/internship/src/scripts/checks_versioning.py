#!/usr/bin/env python3
"""Проверки task_104: версии формата обмена (зеркало ПроверитьВерсиюПакета).

Приёмник понимает 1 и 2: v1 конвертируется, v2 принимается, v3 от
обновившегося источника отклоняется с понятной ошибкой и не калечится.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_versioning.py
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

SUPPORTED = (1, 2)
CURRENT = 2


def make_message(version: int, with_new_field: bool) -> str:
    root = ET.Element("ПакетОбмена", {"Источник": "RIH", "ВерсияФормата": str(version)})
    item = ET.SubElement(root, "Номенклатура",
                         {"Ид": "g-1", "Артикул": "SKU-1", "Наименование": "Товар"})
    if with_new_field:
        item.set("Группа", "Бакалея")  # поле, появившееся в версии 2
    return ET.tostring(root, encoding="unicode", xml_declaration=True)


def receive(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)
    version = int(root.get("ВерсияФормата", "1"))
    if version not in SUPPORTED:
        raise ValueError(
            f"RIH-422: версия формата {version} не поддерживается приёмником "
            f"(понимаем 1 и {CURRENT}); обновите приёмник по регламенту обменов")
    item = root.find("Номенклатура")
    return {"Артикул": item.get("Артикул"),
            "Группа": item.get("Группа", "Без группы"),  # конвертация v1: значение по умолчанию
            "ВерсияИсточник": version}


def main() -> None:
    converted = receive(make_message(1, with_new_field=False))
    assert converted["Группа"] == "Без группы" and converted["ВерсияИсточник"] == 1
    print("[ok] v1 принята с конвертацией: новое поле получило значение по умолчанию")

    native = receive(make_message(2, with_new_field=True))
    assert native["Группа"] == "Бакалея"
    print("[ok] v2 принята как есть")

    try:
        receive(make_message(3, with_new_field=True))
        raise AssertionError("v3 не должна приниматься")
    except ValueError as err:
        assert "RIH-422" in str(err) and "3" in str(err)
        print(f"[ok] источник впереди приёмника: громкий отказ вместо тихого искажения — {err}")


if __name__ == "__main__":
    main()
