"""L1 · Characterization-тесты легаси-расчёта цены (task_218).

Поведение зафиксировано числами, включая артефакты двоичной арифметики и баги.
Эти тесты — страховка рефакторинга (task_219): менять структуру можно, поведение
нельзя.

Оригинал: internship/legacy/LegacyPriceModule.bsl
Порт:     internship/legacy/legacy_rules.py
Разбор:   internship/legacy/NOTES.md
"""
import sys
from datetime import date
from pathlib import Path

import pytest

LEGACY_ROOT = Path(__file__).resolve().parents[2] / "legacy"
sys.path.insert(0, str(LEGACY_ROOT))

from legacy_rules import Client, Product, Warehouse, calculate_batch, calculate_price  # noqa: E402

pytestmark = pytest.mark.legacy


@pytest.fixture
def product() -> Product:
    return Product(article="SKU-00001", price_retail=10.0, price_wholesale=8.0, cost=0.0, group="Прочее")


class TestБазовыйВыборЦены:
    def test_товар_не_передан_даёт_ноль(self):
        assert calculate_price(None, "Розница", 1) == 0.0

    def test_розница(self, product):
        assert calculate_price(product, "Розница", 1) == 10.0

    def test_опт(self, product):
        assert calculate_price(product, "Опт", 1) == 8.0

    def test_акция_даёт_минус_20_процентов_от_розницы(self, product):
        assert calculate_price(product, "Акция", 1) == 8.0

    def test_неизвестный_тип_цены_молча_трактуется_как_розница(self, product):
        """СТРАННОСТЬ оригинала: ошибки нет, цена берётся розничная."""
        assert calculate_price(product, "Специальная", 1) == 10.0
        assert calculate_price(product, "", 1) == 10.0


class TestСкидкиЗаКоличество:
    def test_больше_десяти_минус_три_процента(self, product):
        # 10 * 0.97 = 9.70 в десятичной арифметике, но оригинал округляет через int()
        assert calculate_price(product, "Розница", 11) == 9.69

    def test_больше_пяти_минус_один_процент(self, product):
        assert calculate_price(product, "Розница", 6) == 9.9

    def test_ровно_пять_без_скидки(self, product):
        assert calculate_price(product, "Розница", 5) == 10.0

    def test_ровно_десять_даёт_скидку_один_процент(self, product):
        assert calculate_price(product, "Розница", 10) == 9.9

    def test_границы_строгие(self, product):
        assert calculate_price(product, "Розница", 5.0001) == 9.9
        assert calculate_price(product, "Розница", 10.0001) == 9.69


class TestКлиентскиеСкидки:
    def test_дилер_минус_десять_процентов(self, product):
        assert calculate_price(product, "Розница", 1, Client(kind="Дилер")) == 9.0

    def test_постоянный_получает_скидку_только_при_сумме_больше_500(self, product):
        assert calculate_price(product, "Розница", 1, Client(kind="Постоянный")) == 10.0
        assert calculate_price(product, "Розница", 100, Client(kind="Постоянный")) == 9.02

    def test_порог_постоянного_считается_от_цены_со_скидкой_за_количество(self, product):
        """СТРАННОСТЬ: порог 500 проверяется по цене ПОСЛЕ скидки за количество."""
        # 100 * (10 * 0.97) = 970 > 500 → применяется 0.93
        assert calculate_price(product, "Розница", 100, Client(kind="Постоянный")) == 9.02

    def test_персональная_скидка_в_процентах(self):
        assert calculate_price(Product("S", 100.0), "Розница", 1, Client(personal_discount=10)) == 90.0

    def test_персональная_скидка_применяется_поверх_скидки_дилера(self, product):
        # 10 * 0.9 = 9.0; 9.0 * 0.95 = 8.55 → int(854.99...) = 854 → 8.54
        assert calculate_price(product, "Розница", 1, Client(kind="Дилер", personal_discount=5)) == 8.54

    def test_клиент_без_вида_и_скидки_ничего_не_меняет(self, product):
        assert calculate_price(product, "Розница", 1, Client()) == 10.0

    def test_отрицательная_персональная_скидка_игнорируется(self, product):
        """СТРАННОСТЬ: применяется только при `ПерсональнаяСкидка > 0`, отрицательная молча отбрасывается."""
        assert calculate_price(product, "Розница", 1, Client(personal_discount=-10)) == 10.0
        assert calculate_price(product, "Розница", 1, Client(personal_discount=0)) == 10.0


class TestВесовойТовар:
    def test_рц_минск_не_меняет_цену(self):
        weighted = Product("S", 12.34, is_weight=True)
        assert calculate_price(weighted, "Розница", 1, None, Warehouse("РЦ-Минск")) == 12.34

    def test_другой_склад_сохраняет_цену_но_проходит_через_деление(self):
        weighted = Product("S", 12.34, is_weight=True)
        assert calculate_price(weighted, "Розница", 1, None, Warehouse("Склад-2")) == 12.34

    def test_без_склада_ветка_деления_тоже_выполняется(self):
        weighted = Product("S", 12.34, is_weight=True)
        assert calculate_price(weighted, "Розница", 1) == 12.34


class TestНадбавкаПоДате:
    def test_бакалея_с_2026_года_плюс_пять_процентов(self):
        assert calculate_price(Product("S", 10.0, group="Бакалея"), "Розница", 1,
                               on_date=date(2026, 1, 1)) == 10.5

    def test_до_2026_года_надбавки_нет(self):
        assert calculate_price(Product("S", 10.0, group="Бакалея"), "Розница", 1,
                               on_date=date(2025, 12, 31)) == 10.0

    def test_другая_группа_не_затрагивается(self, product):
        assert calculate_price(product, "Розница", 1, on_date=date(2026, 6, 1)) == 10.0

    def test_без_даты_надбавка_не_применяется(self):
        assert calculate_price(Product("S", 10.0, group="Бакалея"), "Розница", 1) == 10.0


class TestОкруглениеИСебестоимость:
    def test_округление_вниз_до_копейки(self):
        # 10.999 → int(1099.9) = 1099 → 10.99
        assert calculate_price(Product("S", 10.999), "Розница", 1) == 10.99

    def test_цена_ниже_себестоимости_поднимается_на_один_процент(self):
        assert calculate_price(Product("S", 5.0, cost=10.0), "Розница", 1) == 10.1

    def test_цена_равная_себестоимости_не_поднимается(self):
        assert calculate_price(Product("S", 10.0, cost=10.0), "Розница", 1) == 10.0

    def test_отрицательная_розница_даёт_ноль_через_ветку_себестоимости(self):
        """Себестоимость 0, цена -5 < 0 → поднимается до 0 * 1.01 = 0."""
        assert calculate_price(Product("S", -5.0, cost=0.0), "Розница", 1) == 0.0


class TestПакетныйРасчёт:
    def test_количество_всегда_один(self, product):
        """БАГ оригинала: скидка за количество в пакете не применяется."""
        lines = calculate_batch([product], "Розница")
        assert len(lines) == 1
        assert lines[0].price == 10.0
        assert calculate_price(product, "Розница", 11) == 9.69

    def test_клиент_и_склад_в_пакете_учитываются(self, product):
        lines = calculate_batch([product], "Розница", Client(kind="Дилер"), Warehouse("РЦ-Минск"))
        assert lines[0].price == 9.0

    def test_пустой_список_даёт_пустой_результат(self):
        assert calculate_batch([], "Розница") == []

    def test_порядок_товаров_сохраняется(self):
        products = [Product(f"SKU-{i}", 10.0 + i) for i in range(5)]
        lines = calculate_batch(products, "Розница")
        assert [line.product.article for line in lines] == [f"SKU-{i}" for i in range(5)]
        assert [line.price for line in lines] == [10.0, 11.0, 12.0, 13.0, 14.0]


class TestКомбинацииПравил:
    @pytest.mark.parametrize("quantity,client,on_date,expected", [
        (1, None, None, 10.0),
        (11, Client(kind="Дилер"), None, 8.73),
        (100, Client(kind="Постоянный"), date(2026, 3, 1), 9.02),
        (1, Client(kind="Постоянный", personal_discount=10), None, 9.0),
        (6, Client(personal_discount=5), date(2026, 1, 1), 9.4),
    ])
    def test_комбинации(self, product, quantity, client, on_date, expected):
        assert calculate_price(product, "Розница", quantity, client, None, on_date) == expected

    def test_акция_с_надбавкой_бакалеи(self):
        product = Product("S", 10.0, group="Бакалея")
        # 10 * 0.8 = 8.0; * 1.05 = 8.4
        assert calculate_price(product, "Акция", 1, on_date=date(2026, 2, 1)) == 8.4
