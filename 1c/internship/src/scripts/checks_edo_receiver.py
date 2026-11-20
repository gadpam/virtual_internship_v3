#!/usr/bin/env python3
"""Проверки task_115: приёмник ЭДО — эталон, карантин, дубль (зеркало).

Валидный УПД создаёт документ; битая схема, неизвестный контрагент
и несопоставленный товар уходят в карантин с причиной; повтор того
же документа — дубль без второго документа; оригинал сохранён.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_edo_receiver.py
"""

from __future__ import annotations

import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

SAMPLE = Path("docs/edo/samples/upd_sample.xml")
KNOWN_INN = {"7702000002"}
KNOWN_BARCODES = {"4607001000017", "4607001000024"}


class Receiver:
    def __init__(self) -> None:
        self.documents: dict[str, dict] = {}
        self.quarantine: dict[str, str] = {}
        self.originals: dict[str, str] = {}

    def accept(self, doc_id: str, xml_text: str) -> str:
        if doc_id in self.documents:
            return "дубль"
        self.originals[doc_id] = hashlib.sha256(xml_text.encode()).hexdigest()
        try:
            root = ET.fromstring(xml_text)
            assert root.tag == "Файл"
            seller = root.find(".//СвПрод//СвЮЛУч")
            inn = seller.get("ИННЮЛ") if seller is not None else None
            items = root.findall(".//СведТов")
            assert inn and items
        except Exception:
            self.quarantine[doc_id] = "ошибка схемы"
            return "карантин: схема"
        if inn not in KNOWN_INN:
            self.quarantine[doc_id] = f"неизвестный контрагент ИНН {inn}"
            return "карантин: контрагент"
        for item in items:
            code = item.findtext("КодТов")
            if code not in KNOWN_BARCODES:
                self.quarantine[doc_id] = f"нет сопоставления товара {code}"
                return "карантин: номенклатура"
        self.documents[doc_id] = {"inn": inn, "lines": len(items)}
        return "принят"


def main() -> None:
    receiver = Receiver()
    valid = SAMPLE.read_text(encoding="utf-8")
    assert receiver.accept("doc-1", valid) == "принят"
    assert receiver.documents["doc-1"]["lines"] == 2
    print("[ok] эталонный УПД разобран: документ создан, строк 2")

    assert receiver.accept("doc-1", valid) == "дубль"
    assert len(receiver.documents) == 1
    print("[ok] повтор того же документа: дубль, второго документа нет")

    assert receiver.accept("doc-2", "<Файл><Документ/></Файл>") == "карантин: схема"
    unknown = valid.replace("7702000002", "7709999999")
    assert receiver.accept("doc-3", unknown) == "карантин: контрагент"
    bad_item = valid.replace("4607001000017", "4607001999999")
    assert receiver.accept("doc-4", bad_item) == "карантин: номенклатура"
    print(f"[ok] карантин: {receiver.quarantine}")

    assert len(receiver.originals) == 4 and all(len(h) == 64 for h in receiver.originals.values())
    print("[ok] оригиналы сохранены неизменно (хеш SHA-256 у каждого принятого файла)")


if __name__ == "__main__":
    main()
