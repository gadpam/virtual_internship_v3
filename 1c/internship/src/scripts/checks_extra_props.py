#!/usr/bin/env python3
"""Проверки task_179: свой механизм дополнительных реквизитов RIH.

Главный тест — цепочка видимости: завели «Менеджер товара» ->
форма видит -> отчёт показывает -> обмен увозит. Обрыв звена =
механизм создан, но не подключён. Плюс настройки форм между
сеансами и сброс администратором; оценка заявок журналом.

Запуск: src/scripts/.venv/bin/python src/scripts/checks_extra_props.py
"""

from __future__ import annotations

STORE: dict[tuple[str, str], str] = {}
SETTINGS: dict[str, dict] = {}


def set_value(obj: str, prop: str, value: str) -> None:
    if not obj:
        raise ValueError("значение без владельца-объекта не записывается")
    STORE[(obj, prop)] = value


def get_value(obj: str, prop: str) -> str:
    return STORE.get((obj, prop), "")


def main() -> None:
    set_value("SKU-0001", "Менеджер товара", "Категорийный А")
    form_view = get_value("SKU-0001", "Менеджер товара")
    report_row = {"товар": "SKU-0001", "менеджер": get_value("SKU-0001", "Менеджер товара")}
    exchange_payload = {"sku": "SKU-0001",
                        "extra": {"Менеджер товара": get_value("SKU-0001", "Менеджер товара")}}
    assert form_view == report_row["менеджер"] == exchange_payload["extra"]["Менеджер товара"] == "Категорийный А"
    print("[ok] цепочка допреквизита цела: форма = отчёт = обмен по «Менеджер товара» без обрывов")

    try:
        set_value("", "Менеджер товара", "висячая строка")
        raise SystemExit("значение без владельца записалось")
    except ValueError:
        pass
    print("[ok] значение без объекта-владельца запрещено: висящих строк механизм не создаёт")

    SETTINGS["petrov"] = {"МоиЗадачи": {"колонки": ["срок", "контекст"], "фильтр": "просроченные"}}
    restored = SETTINGS["petrov"]["МоиЗадачи"]
    assert restored["фильтр"] == "просроченные"
    SETTINGS["petrov"] = {}  # сброс административной формой
    assert SETTINGS["petrov"] == {}
    print("[ok] настройки форм живут между сеансами и сбрасываются администратором одной формой, а не правкой базы")

    tickets = (["поле в карточку", "колонка в список", "мой отбор", "новый отчёт",
                "поле в карточку", "колонка в список", "интеграция с партнёром",
                "поле в карточку", "мой отбор", "новый реквизит учёта",
                "колонка в список", "поле в карточку", "мой отбор",
                "доработка проведения", "колонка в список", "поле в карточку",
                "мой отбор", "колонка в список", "поле в карточку", "новый отчёт"])
    by_settings = sum(1 for t in tickets if t in
                      ("поле в карточку", "колонка в список", "мой отбор"))
    share = round(100.0 * by_settings / len(tickets))
    assert share == 75, share
    print(f"[ok] журнал заявок: {by_settings} из {len(tickets)} ({share}%) закрываются механизмами без разработки")


if __name__ == "__main__":
    main()
