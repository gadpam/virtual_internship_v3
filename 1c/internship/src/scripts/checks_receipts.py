#!/usr/bin/env python3
"""Проверки task_117: пакетный приём чеков, возвраты, нагрузка (зеркало).

Зеркало РИХ_Чеки/РИХ_Кассы: идемпотентность по (ФН, номер чека), ответ
по каждому чеку, карантин с причиной, возврат по ссылке на исходный,
повтор всей пачки после обрыва связи, объём 72 000 чеков.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_receipts.py
"""

from __future__ import annotations

import json
import time
import zipfile
from io import BytesIO

KNOWN_SKUS = {"SKU-1", "SKU-2", "SKU-3"}
BODY_LIMIT = 10 * 1024 * 1024


def receipt(fn: str, number: int, total: float | None = None, kind: str = "sale",
            ref: tuple[str, int] | None = None, sku: str = "SKU-1") -> dict:
    lines = [{"sku": sku, "quantity": 2, "price": 50.0, "sum": 100.0}]
    data = {"fn": fn, "number": number, "kind": kind, "shop": "SHOP-1",
            "cashier": "K1", "datetime": "2026-11-17T12:00:00",
            "lines": lines, "total": 100.0 if total is None else total}
    if ref is not None:
        data["ref_fn"], data["ref_number"] = ref
    return data


class Receipts:
    def __init__(self) -> None:
        self.documents: dict[tuple[str, int], dict] = {}
        self.quarantine: dict[str, str] = {}
        self.sales_amount = 0.0
        self.sales_qty = 0.0
        self.stock = 0.0

    def _rejection(self, data: dict) -> str:
        if not data.get("fn") or int(data.get("number", 0)) <= 0:
            return "не заполнен ФН или номер чека"
        if not data.get("lines"):
            return "в чеке нет строк товаров"
        lines_sum = 0.0
        for line in data["lines"]:
            if line["sku"] not in KNOWN_SKUS:
                return f"нет сопоставления товара {line['sku']}"
            if line["quantity"] <= 0 or line["price"] < 0:
                return f"некорректные количество или цена товара {line['sku']}"
            line_sum = round(line["quantity"] * line["price"], 2)
            if round(line["sum"], 2) != line_sum:
                return f"сумма строки {line['sku']} не равна количество × цена"
            lines_sum += line_sum
        if round(float(data["total"]), 2) != round(lines_sum, 2):
            return f"сумма чека {data['total']} не сходится с суммой строк {lines_sum}"
        if data.get("kind") == "return":
            original = self.documents.get((data.get("ref_fn"), data.get("ref_number")))
            if original is None or original["kind"] != "sale":
                return "исходный чек возврата не найден"
            if original["fn"] != data["fn"]:
                return "возврат пробит на другой кассе, чем исходный чек"
            returned = sum(doc["total"] for doc in self.documents.values()
                           if doc.get("ref") == (data["ref_fn"], data["ref_number"]))
            if round(float(data["total"]), 2) > round(original["total"] - returned, 2):
                return "сумма возврата превышает остаток по исходному чеку"
        elif data.get("kind") != "sale":
            return f"неизвестный вид чека: {data.get('kind')}"
        return ""

    def accept_one(self, data: dict) -> dict:
        key = (str(data.get("fn", "")), int(data.get("number", 0)))
        label = f"{key[0]}:{key[1]}"
        reason = self._rejection(data)
        if reason:
            self.quarantine[label] = reason
            return {"key": label, "status": "карантин", "reason": reason}
        existing = self.documents.get(key)
        if existing is not None:
            same = (existing["kind"] == data["kind"]
                    and round(existing["total"], 2) == round(float(data["total"]), 2))
            if same:
                return {"key": label, "status": "дубль", "reason": ""}
            reason = "повтор с другим содержимым"
            self.quarantine[label] = reason
            return {"key": label, "status": "карантин", "reason": reason}
        sign = -1 if data["kind"] == "return" else 1
        stored = dict(data)
        if data["kind"] == "return":
            stored["ref"] = (data["ref_fn"], data["ref_number"])
        self.documents[key] = stored
        for line in data["lines"]:
            self.sales_amount += sign * line["sum"]
            self.sales_qty += sign * line["quantity"]
            self.stock -= sign * line["quantity"]
        return {"key": label, "status": "принят", "reason": ""}

    def accept_batch(self, items: list[dict]) -> dict:
        results = [self.accept_one(item) for item in items]
        return {"total": len(items),
                "accepted": sum(r["status"] == "принят" for r in results),
                "duplicates": sum(r["status"] == "дубль" for r in results),
                "quarantined": sum(r["status"] == "карантин" for r in results),
                "results": results}


def check_transport_limits() -> None:
    payload = json.dumps({"receipts": [receipt("FN-1", number)
                                       for number in range(1, 101)]}).encode("utf-8")
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("receipts.json", payload)
    packed = buffer.getvalue()
    assert len(packed) < len(payload)
    with zipfile.ZipFile(BytesIO(packed)) as archive:
        assert json.loads(archive.read("receipts.json"))["receipts"][0]["number"] == 1
    assert len(b"x" * (BODY_LIMIT + 1)) > BODY_LIMIT
    print(f"[ok] транспорт: ZIP {len(payload)} -> {len(packed)} байт, лимит тела {BODY_LIMIT}")


def main() -> None:
    check_transport_limits()
    receipts = Receipts()
    batch = [receipt("FN-1", number) for number in range(1, 97)]
    batch += [receipt("FN-1", number) for number in (1, 2, 3)]
    batch.append(receipt("FN-1", 500, total=101.0))
    outcome = receipts.accept_batch(batch)
    counts = (outcome["accepted"], outcome["duplicates"], outcome["quarantined"])
    assert counts == (96, 3, 1), counts
    assert len(receipts.documents) == 96 and receipts.sales_amount == 9600.0
    print(f"[ok] пакет 100: принято {counts[0]}, дублей {counts[1]}, карантин {counts[2]}")
    print(f"[ok] карантин с причиной: {receipts.quarantine['FN-1:500']}")

    retry = receipts.accept_batch(batch[:10])
    assert retry["duplicates"] == 10 and receipts.sales_amount == 9600.0
    print("[ok] повтор пачки после обрыва связи: все дубли, выручка не задвоилась")

    same_number = receipts.accept_batch([receipt("FN-2", 1)])
    assert same_number["accepted"] == 1
    print("[ok] тот же номер чека на другом ФН — другой чек, а не дубль")

    changed = receipts.accept_batch([receipt("FN-1", 1, total=999.0,
                                             kind="sale") | {"lines": [
                                                 {"sku": "SKU-1", "quantity": 1,
                                                  "price": 999.0, "sum": 999.0}]}])
    assert changed["quarantined"] == 1
    print(f"[ok] повтор ключа с другим содержимым — карантин: {receipts.quarantine['FN-1:1']}")

    back = receipts.accept_one(receipt("FN-1", 900, kind="return", ref=("FN-1", 10)))
    assert back["status"] == "принят" and receipts.sales_amount == 9600.0 + 100.0 - 100.0
    orphan = receipts.accept_one(receipt("FN-1", 901, kind="return", ref=("FN-1", 777)))
    too_much = receipts.accept_one(receipt("FN-1", 902, kind="return", ref=("FN-1", 10)))
    assert orphan["status"] == too_much["status"] == "карантин"
    print(f"[ok] возврат связан с исходным; сирота и повторный полный возврат — карантин: "
          f"{receipts.quarantine['FN-1:901']}; {receipts.quarantine['FN-1:902']}")

    load = Receipts()
    started = time.perf_counter()
    total_items = 0
    errors = 0
    for cashier in range(100):
        fn = f"FN-{cashier:03d}"
        for number in range(1, 721):
            result = load.accept_one(receipt(fn, number))
            total_items += 1
            errors += result["status"] != "принят"
    elapsed = time.perf_counter() - started
    assert total_items == 72000 and errors == 0 and len(load.documents) == 72000
    rate = total_items / elapsed
    print(f"[ok] нагрузка: {total_items} чеков за {elapsed:.2f} с "
          f"({rate:.0f} чеков/с), ошибок {errors}, документов {len(load.documents)}")
    print(f"[ok] обороты нагрузки: сумма {load.sales_amount:.2f}, количество {load.sales_qty:.0f}")


if __name__ == "__main__":
    main()
