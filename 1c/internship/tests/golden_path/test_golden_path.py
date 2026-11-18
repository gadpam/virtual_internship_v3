"""L3 · Золотой путь года: «день из жизни холдинга» (task_302).

Пятнадцать шагов от заказа в онлайн-магазине до закрытия задачи в трекере.
Каждый шаг — действие плюс проверка; провал сообщает номер шага, чтобы в CI
было видно, где именно порвалась цепочка.

Отрицательная ветка — в NEGATIVE_BRANCH.md и в test_negative_branch ниже.
"""
import json
import pathlib
import uuid
from datetime import datetime, timezone

import pytest

pytestmark = [pytest.mark.golden_path, pytest.mark.usefixtures("require_stand")]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
ORDERS = json.loads((FIXTURES / "orders_valid.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def run_id():
    return f"GOLD-{uuid.uuid4().hex[:8].upper()}"


@pytest.fixture(scope="module")
def headers_for(shop, loyalty, tk, tracker):
    return {
        "shop": {"X-Api-Key": shop.api_key, "Content-Type": "application/json"},
        "loyalty": {"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"},
        "tk": {"X-Api-Key": tk.api_key, "Content-Type": "application/json"},
        "tracker": {"X-Api-Key": tracker.api_key, "Content-Type": "application/json"},
    }


def step(number, description):
    """Пометка шага: при падении в отчёте видно, какой именно шаг сломан."""
    return f"шаг {number} ({description})"


def test_golden_path_day_in_the_life(client, shop, loyalty, tk, tracker, run_id, headers_for):
    order_body = ORDERS[0]
    external_id = f"{run_id}-ORDER"
    card = f"CARD-{run_id}"
    h = headers_for

    # 1. Каталог доступен магазину
    products = client.get(f"{shop.base}/api/v1/products", headers=h["shop"], params={"limit": 10}).json()
    assert products["total"] > 0, step(1, "каталог пуст")

    # 2. 1С выгружает цены и остатки в магазин
    upload = client.put(f"{shop.base}/api/v1/products", headers=h["shop"],
                        json=[{"external_id": f"ext-{run_id}", "sku": order_body["lines"][0]["sku"],
                               "name": "Товар золотого пути", "group": "Учебные товары",
                               "price": order_body["lines"][0]["price"], "currency": "BYN",
                               "changed_at": datetime.now(timezone.utc).isoformat()}])
    assert upload.status_code == 200, step(2, "выгрузка каталога")
    assert upload.json()["accepted"] == 1, step(2, "выгрузка принята частично")

    # 3. Магазин создаёт заказ
    created = client.post(f"{shop.base}/api/v1/orders",
                          headers={**h["shop"], "Idempotency-Key": uuid.uuid4().hex},
                          json={"external_id": external_id, "customer_ref": order_body["customer_ref"],
                                "lines": order_body["lines"]})
    assert created.status_code == 201, step(3, "заказ не создан")
    order = created.json()
    assert order["total"] == pytest.approx(order_body["expected_total"], abs=0.01), step(3, "сумма заказа")

    # 4. Резерв товара
    assert client.patch(f"{shop.base}/api/v1/orders/{external_id}/status", headers=h["shop"],
                        params={"status": "reserved"}).json()["status"] == "reserved", step(4, "резерв")

    # 5. Остатки уходят обратно в магазин
    stock = client.get(f"{shop.base}/api/v1/stock", headers=h["shop"],
                       params={"warehouse": "РЦ-Минск"}).json()
    assert any(item["sku"] == order_body["lines"][0]["sku"] for item in stock["items"]), step(5, "остатки")

    # 6. Начисление бонусов (5% от суммы заказа)
    operation_id = f"OP-{run_id}"
    accrual = client.post(f"{loyalty.base}/api/v1/accrue", headers=h["loyalty"],
                          json={"operation_id": operation_id, "card": card,
                                "points": round(order["total"] * 0.05, 2),
                                "reason": f"Бонус за заказ {external_id}"}).json()
    assert accrual["duplicate"] is False, step(6, "бонусы начислены дважды")

    # 7. Повторная доставка того же сообщения не начисляет бонусы повторно
    repeat = client.post(f"{loyalty.base}/api/v1/accrue", headers=h["loyalty"],
                         json={"operation_id": operation_id, "card": card,
                               "points": round(order["total"] * 0.05, 2)}).json()
    assert repeat["duplicate"] is True, step(7, "идемпотентность бонусов")

    # 8. Баланс карты отражает единственное начисление
    balance = client.get(f"{loyalty.base}/api/v1/cards/{card}/balance", headers=h["loyalty"]).json()
    assert balance["balance"] == pytest.approx(100 + order["total"] * 0.05, abs=0.01), step(8, "баланс карты")

    # 9. Расчёт стоимости доставки
    price = client.post(f"{tk.base}/api/v1/calculate", headers=h["tk"],
                        json={"city_to": "Брест", "weight_kg": 2.5, "volume_m3": 0.03,
                              "declared_value": order["total"]}).json()
    assert price["price"] > 0 and price["currency"] == "BYN", step(9, "расчёт доставки")

    # 10. Заявка в транспортную компанию
    shipment = client.post(f"{tk.base}/api/v1/shipments", headers=h["tk"],
                           json={"external_id": external_id, "city_to": "Брест", "weight_kg": 2.5,
                                 "comment": "золотой путь года"}).json()
    assert shipment["duplicate"] is False, step(10, "заявка доставки")

    # 11. Этикетка получена
    label = client.get(f"{tk.base}/api/v1/shipments/{shipment['shipmentId']}/label", headers=h["tk"]).json()
    assert label["labelFormat"] == "pdf-stub", step(11, "этикетка")

    # 12. Доставка завершена
    statuses = [client.get(f"{tk.base}/api/v1/shipments/{shipment['shipmentId']}",
                           headers=h["tk"]).json()["status"] for _ in range(2)]
    assert statuses[-1] == "delivered", step(12, "статусы доставки")

    # 13. Заказ закрыт в магазине
    assert client.patch(f"{shop.base}/api/v1/orders/{external_id}/status", headers=h["shop"],
                        params={"status": "delivered"}).json()["status"] == "delivered", step(13, "закрытие заказа")

    # 14. Контрольная задача в трекере создана и доведена до resolved
    issue = client.post(f"{tracker.base}/api/v1/issues", headers=h["tracker"],
                        json={"external_ref": f"РИХ_Контроль/{run_id}",
                              "title": f"Контроль сквозного сценария {run_id}",
                              "description": "золотой путь года: заказ, бонусы, доставка",
                              "priority": "medium", "assignee": "intern", "due_in_hours": 8}).json()
    client.post(f"{tracker.base}/api/v1/issues/{issue['issueId']}/comments", headers=h["tracker"],
                json={"author": "intern", "text": f"Сценарий пройден, заказ {external_id}"})
    for target in ("in_progress", "resolved"):
        result = client.patch(f"{tracker.base}/api/v1/issues/{issue['issueId']}", headers=h["tracker"],
                              json={"status": target})
        assert result.status_code == 200, step(14, f"переход задачи в {target}")

    # 15. Итог: SLA не нарушено, задача видна в отчёте
    card_view = client.get(f"{tracker.base}/api/v1/issues/{issue['issueId']}", headers=h["tracker"]).json()
    assert card_view["status"] == "resolved", step(15, "состояние задачи")
    assert len(card_view["comments"]) == 1, step(15, "журнал разбора")
    sla = client.get(f"{tracker.base}/api/v1/sla", headers=h["tracker"]).json()
    assert all(item["issueId"] != issue["issueId"] for item in sla["items"]), step(15, "нарушение SLA")


def test_negative_branch_partner_down(client, shop, loyalty, tracker, run_id, headers_for):
    """Негативная ветка: партнёр лежит — заказ не потерян, создан инцидент (task_302)."""
    h = headers_for
    external_id = f"{run_id}-NEG"

    # 1. Заказ принят, пока магазин жив
    created = client.post(f"{shop.base}/api/v1/orders",
                          headers={**h["shop"], "Idempotency-Key": uuid.uuid4().hex},
                          json={"external_id": external_id, "lines": ORDERS[0]["lines"]})
    assert created.status_code == 201

    # 2. Лояльность недоступна: операция не выполнена
    failing = client.post(f"{loyalty.base}/api/v1/accrue",
                          headers={**h["loyalty"], "X-Fault-Mode": "error500"},
                          json={"operation_id": f"OP-{external_id}", "card": f"CARD-{run_id}-NEG", "points": 5.0})
    assert failing.status_code == 500

    # 3. Создан инцидент: данные о ненайденной операции не потеряны
    issue = client.post(f"{tracker.base}/api/v1/issues", headers=h["tracker"],
                        json={"external_ref": f"РИХ_Инцидент/{external_id}",
                              "title": "Лояльность недоступна при начислении бонусов",
                              "description": f"Заказ {external_id}: операция OP-{external_id} не выполнена, 500",
                              "priority": "high", "due_in_hours": 4}).json()
    assert issue["status"] == "new"

    # 4. Партнёр вернулся: операция доставлена ровно один раз
    retry = client.post(f"{loyalty.base}/api/v1/accrue", headers=h["loyalty"],
                        json={"operation_id": f"OP-{external_id}", "card": f"CARD-{run_id}-NEG", "points": 5.0})
    assert retry.status_code == 200
    assert retry.json()["duplicate"] is False

    # 5. Инцидент закрыт с комментарием о причине
    client.post(f"{tracker.base}/api/v1/issues/{issue['issueId']}/comments", headers=h["tracker"],
                json={"author": "dezhurnyy", "text": "Партнёр восстановлен, операция доставлена, дублей нет"})
    for target in ("in_progress", "resolved", "closed"):
        assert client.patch(f"{tracker.base}/api/v1/issues/{issue['issueId']}", headers=h["tracker"],
                            json={"status": target}).status_code == 200
