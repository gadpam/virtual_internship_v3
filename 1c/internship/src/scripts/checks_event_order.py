#!/usr/bin/env python3
"""Проверки task_112: порядок событий и сверка (зеркало).

Дубль поглощается, событие не по порядку проигрывает применённому,
устаревшее отклоняется; ночная сверка находит искусственное
расхождение и исправляет его от master (RIH).

Запуск: src/scripts/.venv/bin/python src/scripts/checks_event_order.py
"""

from __future__ import annotations


class StockEvents:
    def __init__(self) -> None:
        self.state: dict[str, tuple[float, str]] = {}  # sku -> (qty, moment)
        self.applied: set[str] = set()

    def apply(self, event_id: str, sku: str, qty: float, version: int, moment: str) -> str:
        if event_id in self.applied:
            return "дубль"
        if version != 1:
            raise ValueError(f"RIH-422: версия события {version} не поддерживается")
        current_moment = self.state.get(sku, (0.0, ""))[1]
        if moment <= current_moment:
            return "устарело"
        self.state[sku] = (qty, moment)
        self.applied.add(event_id)
        return "применено"


def main() -> None:
    events = StockEvents()
    assert events.apply("e1", "SKU-1", 100, 1, "2026-11-17T10:00:00") == "применено"
    assert events.apply("e1", "SKU-1", 100, 1, "2026-11-17T10:00:00") == "дубль"
    print("[ok] дубль события поглощён: состояние применено один раз")

    assert events.apply("e2", "SKU-1", 90, 1, "2026-11-17T11:00:00") == "применено"
    assert events.apply("e3", "SKU-1", 95, 1, "2026-11-17T10:30:00") == "устарело"
    assert events.state["SKU-1"][0] == 90
    print("[ok] событие не по порядку проиграло: остаток 90, а не воскресшие 95")

    try:
        events.apply("e4", "SKU-1", 1, 2, "2026-11-17T12:00:00")
        raise AssertionError("версия 2 не должна применяться")
    except ValueError as err:
        assert "RIH-422" in str(err)
    print("[ok] неизвестная версия события отклонена до применения")

    shop_state = {"SKU-1": 90.0, "SKU-2": 5.0}   # витрина
    rih_state = {"SKU-1": 90.0, "SKU-2": 7.0}    # master
    diff = {sku for sku in set(shop_state) | set(rih_state)
            if shop_state.get(sku) != rih_state.get(sku)}
    assert diff == {"SKU-2"}, diff
    for sku in diff:  # автоисправление по правилу master
        shop_state[sku] = rih_state[sku]
    assert shop_state == rih_state
    print(f"[ok] сверка нашла расхождение {diff} и исправила от master: витрина сошлась")


if __name__ == "__main__":
    main()
