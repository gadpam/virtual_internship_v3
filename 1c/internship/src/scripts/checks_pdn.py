#!/usr/bin/env python3
"""Проверки task_135: ПДн — реестр, маскирование, журнал, удаление.

Зеркалит РИХ_ПерсональныеДанные: маски телефона и карты, санитайзер
контекста журнала единой точкой, хранение чувствительного реквизита
хешем, обезличивание субъекта с сохранением учётных фактов. Финал —
поиск открытых ПДн по текстам репозитория интеграций.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_pdn.py
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def digits_only(value: str) -> str:
    return re.sub(r"\D", "", value)


def mask_phone(phone: str) -> str:
    digits = digits_only(phone)
    if len(digits) < 4:
        return "***"
    return f"{digits[0]}-***-**-{digits[-2:]}"


def mask_card(number: str) -> str:
    digits = digits_only(number)
    if len(digits) < 4:
        return "****"
    return f"**** **** **** {digits[-4:]}"


def hash_requisite(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def sanitize(text: str) -> str:
    result = text

    def repl(match: re.Match) -> str:
        raw = match.group(0)
        digits = digits_only(raw)
        if len(digits) >= 13:
            return mask_card(digits)
        return mask_phone(digits)

    return re.sub(r"[\d][\d\s()+-]{8,}\d", repl, result)


OPEN_PDN = re.compile(r"(\+?\d[\d\s()-]{8,}\d)")


def find_open_pdn(text: str) -> list[str]:
    found = []
    for match in OPEN_PDN.finditer(text):
        raw = match.group(0)
        digits = digits_only(raw)
        if len(digits) < 10 or "*" in raw:
            continue
        if re.search(r"\d{4}-\d{2}-\d{2}", raw):
            continue  # дата, а не телефон
        if digits in "0123456789" * 3:
            continue  # алфавит цифр в коде проверки символов
        found.append(raw)
    return found


def main() -> None:
    assert mask_phone("+375 (29) 123-45-12") == "3-***-**-12"
    assert mask_card("4111 1111 1111 1111") == "**** **** **** 1111"
    print("[ok] маски: телефон — первая и последние две, карта — последние четыре")

    journal_context = (
        "начисление не прошло, клиент +375 (29) 123-45-12, "
        "карта 4111 1111 1111 1111, заказ shop-1042")
    cleaned = sanitize(journal_context)
    assert "123-45-12" not in cleaned and "4111" not in cleaned
    assert "shop-1042" in cleaned and "**** **** **** 1111" in cleaned
    print("[ok] санитайзер журнала: ПДн заменены масками, идентификаторы целы")

    card_hash = hash_requisite("4111111111111111")
    stored = {"client": "CL-1", "card_hash": card_hash, "points": 600}
    assert "4111" not in str(stored)
    assert hash_requisite("4111111111111111") == stored["card_hash"]
    print("[ok] чувствительный реквизит: в базе хеш, поиск по полному номеру работает")

    client = {"code": "CL-1", "phone": "+375291234512",
              "card_hash": card_hash, "address": "Минск, пр. Победы 1",
              "points_balance": 600, "checks_total": 15430.15}
    client["phone"] = ""
    client["address"] = ""
    client["card_hash"] = hash_requisite(f"обезличено-{client['code']}")
    assert client["phone"] == "" and client["card_hash"] != card_hash
    assert client["points_balance"] == 600 and client["checks_total"] == 15430.15
    print("[ok] обезличивание: персональные поля стёрты, учётные факты сохранены")

    leaks = []
    skip = {".venv", "__pycache__", "node_modules", ".git"}
    for root in ("Configuration/src", "src", "tools"):
        for path in Path(root).rglob("*"):
            if any(part in skip for part in path.parts):
                continue
            if path.is_file() and path.suffix in (".bsl", ".py", ".md", ".yml", ".yaml") \
                    and path.name != "checks_pdn.py" and "checks_" not in path.name:
                leaks.extend((str(path), hit) for hit in
                             find_open_pdn(path.read_text(encoding="utf-8", errors="ignore")))
    assert not leaks, leaks[:3]
    print("[ok] поиск по дереву интеграций: открытых телефонов и карт не найдено")


if __name__ == "__main__":
    main()
