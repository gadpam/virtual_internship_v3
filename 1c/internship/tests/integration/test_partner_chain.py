"""L3 · Интеграционные тесты цепочки партнёров (task_141).

Сценарий соответствует золотому пути: заказ из магазина → начисление бонусов →
заявка в транспортную компанию → статус. Проверяем не «сервис отвечает 200»,
а согласованность данных между системами.
"""
import json
import pathlib
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_stand")]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
ORDERS = json.loads((FIXTURES / "orders_valid.json").read_text(encoding="utf-8"))


def new_external_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


@pytest.mark.parametrize("case", ORDERS["cases"], ids=[c["name"] for c in ORDERS["cases"]])
def test_order_is_created_with_expected_total(client, shop, shop_headers, case):
    external_id = new_external_id("IT")
    payload = {"external_id": external_id, "customer_ref": case["customer_ref"], "lines": case["lines"]}

    response = client.post(f"{shop.base}/api/v1/orders",
                           headers={**shop_headers, "Idempotency-Key": uuid.uuid4().hex}, json=payload)
    assert response.status_code == 201, response.text
    body = response.json()

    assert body["externalId"] == external_id
    assert body["status"] == "new"
    assert body["total"] == pytest.approx(case["expected_total"], abs=0.01)

    # заказ виден в списке — значит, состояние сервиса согласовано с ответом
    listing = client.get(f"{shop.base}/api/v1/orders", headers=shop_headers,
                         params={"status": "new"}).json()
    assert any(item["external_id"] == external_id for item in listing["items"])


def test_full_chain_order_to_loyalty_to_transport(client, shop, loyalty, tk, shop_headers):
    external_id = new_external_id("CHAIN")
    order = client.post(f"{shop.base}/api/v1/orders",
                        headers={**shop_headers, "Idempotency-Key": uuid.uuid4().hex},
                        json={"external_id": external_id,
                              "customer_ref": "cust-1001",
                              "lines": [{"sku": "SKU-00001", "quantity": 2, "price": 12.5}]}).json()

    # 1. Резерв в магазине
    reserved = client.patch(f"{shop.base}/api/v1/orders/{external_id}/status",
                            headers=shop_headers, params={"status": "reserved"}).json()
    assert reserved["status"] == "reserved"

    # 2. Бонусы: сумма начисления выведена из суммы заказа
    operation_id = f"OP-{uuid.uuid4().hex[:12]}"
    accrual = client.post(f"{loyalty.base}/api/v1/accrue",
                          headers={"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"},
                          json={"operation_id": operation_id, "card": "CARD-777",
                                "points": round(order["total"] * 0.05, 2),
                                "reason": f"Бонус за заказ {external_id}"}).json()
    assert accrual["duplicate"] is False
    assert accrual["points"] == pytest.approx(1.25, abs=0.01)

    # 3. Доставка: расчёт стоимости и заявка
    calculation = client.post(f"{tk.base}/api/v1/calculate",
                              headers={"X-Api-Key": tk.api_key, "Content-Type": "application/json"},
                              json={"city_to": "Брест", "weight_kg": 2.5, "volume_m3": 0.03,
                                    "declared_value": order["total"]}).json()
    assert calculation["price"] > 0
    assert calculation["currency"] == "BYN"

    shipment = client.post(f"{tk.base}/api/v1/shipments",
                           headers={"X-Api-Key": tk.api_key, "Content-Type": "application/json"},
                           json={"external_id": external_id, "city_to": "Брест", "weight_kg": 2.5}).json()
    assert shipment["duplicate"] is False
    assert shipment["status"] == "created"

    # 4. Статусы продвигаются: created → in_transit → delivered
    statuses = [client.get(f"{tk.base}/api/v1/shipments/{shipment['shipmentId']}",
                           headers={"X-Api-Key": tk.api_key}).json()["status"] for _ in range(2)]
    assert statuses == ["in_transit", "delivered"]

    # 5. Отгрузка в магазине
    shipped = client.patch(f"{shop.base}/api/v1/orders/{external_id}/status",
                           headers=shop_headers, params={"status": "shipped"}).json()
    assert shipped["status"] == "shipped"


def test_chain_is_repeatable_without_duplicates(client, shop, loyalty, shop_headers):
    """Повтор всей цепочки с теми же ключами не создаёт дублей (task_105)."""
    external_id = new_external_id("REPEAT")
    key = uuid.uuid4().hex
    operation_id = f"OP-{uuid.uuid4().hex[:12]}"
    headers = {**shop_headers, "Idempotency-Key": key}
    body = {"external_id": external_id, "lines": [{"sku": "SKU-00002", "quantity": 1, "price": 2.1}]}

    first = client.post(f"{shop.base}/api/v1/orders", headers=headers, json=body).json()
    second = client.post(f"{shop.base}/api/v1/orders", headers=headers, json=body).json()
    assert first["duplicate"] is False and second["duplicate"] is True

    loyalty_headers = {"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"}
    points = {"operation_id": operation_id, "card": "CARD-888", "points": 3.0}
    balance_before = client.get(f"{loyalty.base}/api/v1/cards/CARD-888/balance", headers=loyalty_headers).json()["balance"]
    client.post(f"{loyalty.base}/api/v1/accrue", headers=loyalty_headers, json=points)
    client.post(f"{loyalty.base}/api/v1/accrue", headers=loyalty_headers, json=points)
    balance_after = client.get(f"{loyalty.base}/api/v1/cards/CARD-888/balance", headers=loyalty_headers).json()["balance"]

    assert balance_after == pytest.approx(balance_before + 3.0, abs=0.01)


def test_reverse_restores_balance_and_is_not_repeatable(client, loyalty):
    headers = {"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"}
    operation_id = f"OP-REV-{uuid.uuid4().hex[:8]}"
    before = client.get(f"{loyalty.base}/api/v1/cards/CARD-999/balance", headers=headers).json()["balance"]

    accrual = client.post(f"{loyalty.base}/api/v1/accrue", headers=headers,
                          json={"operation_id": operation_id, "card": "CARD-999", "points": 10.0}).json()
    assert accrual["balance"] == pytest.approx(before + 10.0, abs=0.01)

    reversed_once = client.post(f"{loyalty.base}/api/v1/reverse", headers=headers,
                                params={"operation_id": operation_id})
    assert reversed_once.status_code == 200
    assert reversed_once.json()["balance"] == pytest.approx(before, abs=0.01)

    assert client.post(f"{loyalty.base}/api/v1/reverse", headers=headers,
                       params={"operation_id": operation_id}).status_code == 409


def test_entrypoint_routes_to_partners(client, entrypoint, shop):
    """Через nginx партнёр доступен по префиксу /shop/ (task_260)."""
    try:
        response = client.get(f"{entrypoint}/shop/health")
    except Exception as error:  # noqa: BLE001
        pytest.skip(f"точка входа недоступна: {error}")
    assert response.status_code == 200
    assert response.json()["service"] == "mock_shop_api"
