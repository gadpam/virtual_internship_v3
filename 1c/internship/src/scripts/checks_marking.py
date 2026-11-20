#!/usr/bin/env python3
"""Проверки task_116: коды маркировки, агрегаты и контроль количества.

Зеркало РИХ_Маркировка: приёмка защищает уникальность и принадлежность
товару, все переходы идут одним конечным автоматом, агрегат двигает
детей, а сверка количества с единичными кодами находит расхождение.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_marking.py
"""

from __future__ import annotations


class MarkingError(ValueError):
    pass


class Marking:
    def __init__(self) -> None:
        self.current: dict[str, dict] = {}
        self.history: list[dict] = []

    @staticmethod
    def _check_input(codes: list[str]) -> None:
        if any(not code.strip() for code in codes):
            raise MarkingError("RIH-422: пустой код")
        if len(codes) != len(set(codes)):
            raise MarkingError("RIH-422: код повторяется во входном списке")

    def _write(self, code: str, product: str, warehouse: str, status: str,
               parent: str, kind: str, reason: str, source: str) -> None:
        record = {"product": product, "warehouse": warehouse, "status": status,
                  "parent": parent, "kind": kind, "reason": reason, "source": source}
        self.current[code] = record
        self.history.append({"code": code, **record})

    def _new_code(self, code: str, product: str, warehouse: str,
                  parent: str, kind: str, source: str) -> None:
        if code in self.current:
            if self.current[code]["product"] != product:
                raise MarkingError(f"RIH-409: код {code} принадлежит другому товару")
            raise MarkingError(f"RIH-409: код уже принят: {code}")
        self._write(code, product, warehouse, "Принят", parent, kind, "", source)

    def accept(self, product: str, warehouse: str, codes: list[str], source: str) -> None:
        self._check_input(codes)
        for code in codes:
            self._new_code(code, product, warehouse, "", "Единица", source)

    def accept_aggregate(self, aggregate: str, product: str, warehouse: str,
                         units: list[str], source: str) -> None:
        self._check_input(units)
        self._new_code(aggregate, product, warehouse, "", "Агрегат", source)
        for code in units:
            self._new_code(code, product, warehouse, aggregate, "Единица", source)

    def _expanded(self, codes: list[str]) -> list[str]:
        result: list[str] = []
        for code in codes:
            if code not in result:
                result.append(code)
            state = self.current.get(code)
            if state and state["kind"] == "Агрегат":
                for child, child_state in self.current.items():
                    if child_state["parent"] == code and child not in result:
                        result.append(child)
        return result

    @staticmethod
    def _allowed(state: dict, new_status: str) -> bool:
        current = state["status"]
        return (
            (current == "Принят" and new_status in ("ВНаличии", "Перемещён", "Выбыл"))
            or (current == "ВНаличии" and new_status in ("Перемещён", "Выбыл"))
            or (current == "Перемещён" and new_status == "ВНаличии")
            or (current == "Выбыл" and new_status == "Возвращён"
                and state["reason"] == "Продажа")
            or (current == "Возвращён" and new_status in ("ВНаличии", "Выбыл"))
        )

    def change(self, codes: list[str], new_status: str, source: str,
               reason: str = "", warehouse: str | None = None) -> int:
        self._check_input(codes)
        changed = 0
        for code in self._expanded(codes):
            state = self.current.get(code)
            if state is None:
                raise MarkingError(f"RIH-422: неизвестный код {code}")
            if not self._allowed(state, new_status):
                raise MarkingError(
                    f"RIH-409: запрещён переход {code}: {state['status']} -> {new_status}")
            new_reason = reason if new_status == "Выбыл" else (
                state["reason"] if new_status == "Возвращён" else "")
            self._write(code, state["product"], warehouse or state["warehouse"],
                        new_status, state["parent"], state["kind"], new_reason, source)
            changed += 1
        return changed

    def discrepancies(self, stock: dict[tuple[str, str], int]) -> list[dict]:
        code_counts: dict[tuple[str, str], int] = {}
        for state in self.current.values():
            if state["kind"] == "Единица" and state["status"] in ("Принят", "ВНаличии"):
                key = (state["product"], state["warehouse"])
                code_counts[key] = code_counts.get(key, 0) + 1
        result = []
        for key in sorted(set(stock) | set(code_counts)):
            quantity = stock.get(key, 0)
            codes = code_counts.get(key, 0)
            if quantity != codes:
                result.append({"product": key[0], "warehouse": key[1],
                               "quantity": quantity, "codes": codes,
                               "difference": quantity - codes})
        return result


def expect_error(action, fragment: str) -> None:
    try:
        action()
    except MarkingError as err:
        assert fragment in str(err), err
        return
    raise AssertionError(f"ожидалась ошибка {fragment}")


def main() -> None:
    marking = Marking()
    marking.accept("SKU-A", "WH-1", ["U1", "U2", "U3"], "Поступление:1")
    marking.accept_aggregate("BOX-1", "SKU-A", "WH-1", ["U4", "U5"], "Поступление:1")
    print("[ok] приёмка: 3 единицы и агрегат из 2 единиц, родитель не единица")

    expect_error(lambda: marking.accept("SKU-B", "WH-1", ["U1"], "Поступление:2"),
                 "принадлежит другому товару")
    expect_error(lambda: marking.accept("SKU-A", "WH-1", ["U6", "U6"], "Поступление:2"),
                 "повторяется во входном списке")
    print("[ok] уникальность: чужой товар и дубль внутри списка отклонены")

    marking.change(["U1", "U2", "U3", "BOX-1"], "ВНаличии", "Размещение:1")
    marking.change(["U1"], "Перемещён", "Перемещение:1")
    marking.change(["U1"], "ВНаличии", "Перемещение:1", warehouse="WH-2")
    marking.change(["U1"], "Выбыл", "Чек:1", reason="Продажа")
    expect_error(lambda: marking.change(["U1"], "Выбыл", "Чек:2", reason="Продажа"),
                 "запрещён переход")
    marking.change(["U1"], "Возвращён", "Возврат:1")
    marking.change(["U1"], "ВНаличии", "РазмещениеВозврата:1")
    print("[ok] продажа, запрет повторной продажи, возврат и размещение возврата")

    marking.change(["U2"], "Выбыл", "Списание:1", reason="Списание")
    expect_error(lambda: marking.change(["U2"], "Возвращён", "Возврат:2"),
                 "запрещён переход")
    expect_error(lambda: marking.change(["UNKNOWN"], "ВНаличии", "Документ:1"),
                 "неизвестный код")
    print("[ok] списанный код не возвращается, неизвестный код не размещается")

    marking.change(["BOX-1"], "Перемещён", "Перемещение:2")
    states = {code: marking.current[code]["status"] for code in ("BOX-1", "U4", "U5")}
    assert states == {"BOX-1": "Перемещён", "U4": "Перемещён", "U5": "Перемещён"}
    marking.change(["BOX-1"], "ВНаличии", "Перемещение:2", warehouse="WH-2")
    marking.change(["BOX-1"], "Выбыл", "Чек:3", reason="Продажа")
    assert all(marking.current[code]["status"] == "Выбыл" for code in states)
    print(f"[ok] агрегат двигает детей одним действием: {states} -> все Выбыл")

    stock = {("SKU-A", "WH-1"): 2, ("SKU-A", "WH-2"): 1}
    diff = marking.discrepancies(stock)
    assert diff == [{"product": "SKU-A", "warehouse": "WH-1", "quantity": 2,
                     "codes": 1, "difference": 1}], diff
    print(f"[ok] контроль нашёл искусственное расхождение: {diff}")
    print(f"[ok] история движения кодов: переходов записано {len(marking.history)}")


if __name__ == "__main__":
    main()
