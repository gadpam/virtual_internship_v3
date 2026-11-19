"""Точный порт поведения legacy/LegacyPriceModule.bsl на Python.

Зачем нужен порт: characterization-тесты (task_218) должны выполняться быстро и
в CI, а прогон 1С-тестов требует платформы. Порт фиксирует правила расчёта цены
в проверяемом виде и служит эталоном, пока вы переписываете модуль на 1С.

ВАЖНО: порт повторяет исходное поведение ВКЛЮЧАЯ странности и баги. Исправлять
его можно только после того, как поведение согласовано с владельцем и зафиксировано
в NOTES.md. Каждое отступление от оригинала помечено комментарием «СТРАННОСТЬ» или «БАГ».
"""
from dataclasses import dataclass
from datetime import date
from typing import List, Optional


@dataclass
class Product:
    article: str
    price_retail: float
    price_wholesale: float = 0.0
    cost: float = 0.0
    is_weight: bool = False
    group: str = ""


@dataclass
class Client:
    kind: str = ""                  # "Дилер" | "Постоянный" | ""
    personal_discount: float = 0.0  # в процентах


@dataclass
class Warehouse:
    code: str = ""


@dataclass
class PriceLine:
    product: Product
    price: float


def calculate_price(
    product: Optional[Product],
    price_type: str,
    quantity: float,
    client: Optional[Client] = None,
    warehouse: Optional[Warehouse] = None,
    on_date: Optional[date] = None,
) -> float:
    """Повторяет РассчитатьЦену() из LegacyPriceModule.bsl построчно."""
    if product is None:
        return 0.0

    if price_type == "Розница":
        price = product.price_retail
    elif price_type == "Опт":
        price = product.price_wholesale
    elif price_type == "Акция":
        price = product.price_retail * 0.8
    else:
        price = product.price_retail          # СТРАННОСТЬ: неизвестный тип цены молча = розница

    if product.is_weight:
        if warehouse is not None and warehouse.code == "РЦ-Минск":
            price = price * 1.0
        else:
            price = price / 1000 * 1000       # СТРАННОСТЬ: операция ничего не меняет, но оставляет след деления

    if quantity > 10:
        price = price * 0.97
    elif quantity > 5:
        price = price * 0.99

    if client is not None:
        if client.kind == "Дилер":
            price = price * 0.9
        elif client.kind == "Постоянный":
            if quantity * price > 500:        # СТРАННОСТЬ: порог считается по цене ДО скидки постоянному
                price = price * 0.93
        if client.personal_discount > 0:
            price = price * (1 - client.personal_discount / 100)

    if on_date is not None and on_date >= date(2026, 1, 1) and product.group == "Бакалея":
        price = price * 1.05                  # СТРАННОСТЬ: надбавка зависит от даты и группы

    price = int(price * 100) / 100            # округление вниз до копейки, как в оригинале
    if price < product.cost:
        price = product.cost * 1.01           # СТРАННОСТЬ: защита от продажи ниже себестоимости + 1%
    if price < 0:
        price = 0.0
    return price


def calculate_batch(products: List[Product], price_type: str, client: Optional[Client] = None,
                    warehouse: Optional[Warehouse] = None, on_date: Optional[date] = None) -> List[PriceLine]:
    """Повторяет РассчитатьЦенуСПакетом(): количество всегда 1.

    БАГ оригинала сохранён намеренно: в пакете скидка за количество не применяется.
    """
    return [
        PriceLine(product=product,
                  price=calculate_price(product, price_type, 1, client, warehouse, on_date))
        for product in products
    ]
