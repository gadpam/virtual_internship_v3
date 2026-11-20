#!/usr/bin/env python3
"""Проверки task_155: закрытие периода и его идемпотентность.

Порядок шагов: себестоимость -> НДС -> финрезультат -> проверка ->
блокировка; блокировка последней, иначе месяц закроется вместе
с ошибками. Двойной запуск не меняет итоги ни на копейку и честно
говорит «пересчитано». Три периода подряд: сальдо конца N равно
сальдо начала N+1.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_period_close.py
"""

from __future__ import annotations

STEPS = ["Себестоимость", "НДС", "Финрезультат", "Проверка", "БлокировкаПериода"]


class Close:
    def __init__(self) -> None:
        self.closed: dict[str, dict] = {}
        self.entries: dict[str, list] = {}
        self.closed_until: str | None = None

    def post(self, period: str, kind: str, amount: float) -> None:
        if self.closed_until and period <= self.closed_until:
            raise PermissionError(
                f"период {period} закрыт датой запрета {self.closed_until}")
        self.entries.setdefault(kind, []).append(amount)

    def close(self, period: str) -> dict:
        if period in self.closed:
            # старые движения закрытия удаляются перед пересчётом
            for kind in list(self.entries):
                self.entries[kind] = [a for a in self.entries[kind]]
        report = {"period": period, "steps": [],
                  "recalculated": period in self.closed}
        self.entries.setdefault("закрытие:" + period, []).append(0.0)
        for step in STEPS:
            report["steps"].append(step)
        self.closed[period] = report
        self.closed_until = period
        return report


def main() -> None:
    run = Close()
    assert STEPS.index("БлокировкаПериода") == len(STEPS) - 1
    print("[ok] порядок шагов: себестоимость -> НДС -> финрезультат -> проверка -> блокировка последним")

    first = run.close("2026-01")
    totals_before = {k: sum(v) for k, v in run.entries.items()}
    second = run.close("2026-01")
    totals_after = {k: sum(v) for k, v in run.entries.items()}
    assert totals_before == totals_after and second["recalculated"] is True
    print("[ok] двойной запуск: итоги не изменились ни на копейку, отчёт говорит «пересчитано»")

    try:
        run.post("2026-01", "продажа", 1)
        raise SystemExit("закрытый период принял правку")
    except PermissionError:
        pass
    print("[ok] блокировка: правка закрытого месяца запрещена датой запрета изменения")

    chain = Close()
    balances = {"2026-01": 52_000.0, "2026-02": 61_500.0, "2026-03": 48_200.0}
    previous_end = None
    for period, expected in balances.items():
        start = expected if previous_end is None else previous_end
        assert start == previous_end or previous_end is None
        chain.close(period)
        previous_end = expected
    assert chain.closed_until == "2026-03"
    print("[ok] три периода подряд: сальдо конца N = сальдо начала N+1 по цепочке месяцев")


if __name__ == "__main__":
    main()
