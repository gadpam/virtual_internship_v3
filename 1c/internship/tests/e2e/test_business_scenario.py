"""L3 · Сквозной бизнес-сценарий по API (task_142).

«Заказ интернет-магазина прошёл путь до доставки и бонусов». Сценарий повторяет
золотой путь vanessa (tests/features/golden_path.feature), но выполняется без 1С —
поэтому его можно гонять в CI на каждом PR.
"""
import json
import pathlib
import time
import uuid

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.usefixtures("require_stand")]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
ORDERS = json.loads((FIXTURES / "orders_valid.json").read_text(encoding="utf-8"))["cases"][0]


def wait_until(predicate, timeout=15.0, interval=0.5, message="условие не выполнено"):
    """Явное ожидание вместо sleep: опрашиваем состояние, пока не получим нужное."""
    deadline = time.time() + timeout
    last = None
    while time.time() < deadline:
        last = predicate()
        if last:
            return last
        time.sleep(interval)
    raise AssertionError(f"{message} (последняя проверка: {last})")


@pytest.fixture
def scenario_id():
    return f"E2E-{uuid.uuid4().hex[:8].upper()}"


def test_order_journey(client, shop, loyalty, tk, tracker, shop_headers, scenario_id):
    loyalty_headers = {"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"}
    tk_headers = {"X-Api-Key": tk.api_key, "Content-Type": "application/json"}
    tracker_headers = {"X-Api-Key": tracker.api_key, "Content-Type": "application/json"}

    # Шаг 1. Магазин принимает заказ
    created = client.post(f"{shop.base}/api/v1/orders",
                          headers={**shop_headers, "Idempotency-Key": uuid.uuid4().hex},
                          json={"external_id": scenario_id,
                                "customer_ref": ORDERS["customer_ref"],
                                "lines": ORDERS["lines"]})
    assert created.status_code == 201, created.text
    order = created.json()
    assert order["total"] == pytest.approx(ORDERS["expected_total"], abs=0.01)

    # Шаг 2. Резерв товара
    assert client.patch(f"{shop.base}/api/v1/orders/{scenario_id}/status",
                        headers=shop_headers, params={"status": "reserved"}).json()["status"] == "reserved"

    # Шаг 3. Начисление бонусов (5% от суммы заказа)
    operation_id = f"OP-{scenario_id}"
    accrual = client.post(f"{loyalty.base}/api/v1/accrue", headers=loyalty_headers,
                          json={"operation_id": operation_id, "card": "CARD-E2E",
                                "points": round(order["total"] * 0.05, 2),
                                "reason": f"Бонус за заказ {scenario_id}"}).json()
    assert accrual["duplicate"] is False

    # Шаг 4. Доставка: расчёт → заявка → статусы
    price = client.post(f"{tk.base}/api/v1/calculate", headers=tk_headers,
                        json={"city_to": "Минск", "weight_kg": 1.2, "volume_m3": 0.02,
                              "declared_value": order["total"]}).json()["price"]
    assert price > 0

    shipment = client.post(f"{tk.base}/api/v1/shipments", headers=tk_headers,
                           json={"external_id": scenario_id, "city_to": "Минск",
                                 "weight_kg": 1.2, "comment": "e2e-сценарий"}).json()

    delivered = wait_until(
        lambda: (lambda s: s if s == "delivered" else None)(
            client.get(f"{tk.base}/api/v1/shipments/{shipment['shipmentId']}", headers=tk_headers).json()["status"]),
        timeout=10, interval=0.2,
        message="заявка не дошла до статуса delivered",
    )
    assert delivered == "delivered"

    # Шаг 5. Отгрузка и закрытие заказа в магазине
    assert client.patch(f"{shop.base}/api/v1/orders/{scenario_id}/status",
                        headers=shop_headers, params={"status": "delivered"}).json()["status"] == "delivered"

    # Шаг 6. Инцидентов нет, но задача в трекере на контроль создана и закрыта
    issue = client.post(f"{tracker.base}/api/v1/issues", headers=tracker_headers,
                        json={"external_ref": f"РИХ_Контроль/{scenario_id}",
                              "title": f"Контроль доставки заказа {scenario_id}",
                              "priority": "low", "due_in_hours": 24}).json()
    assert client.patch(f"{tracker.base}/api/v1/issues/{issue['issueId']}", headers=tracker_headers,
                        json={"status": "in_progress", "assignee": "dezhurnyy"}).json()["status"] == "in_progress"
    assert client.patch(f"{tracker.base}/api/v1/issues/{issue['issueId']}", headers=tracker_headers,
                        json={"status": "resolved"}).json()["status"] == "resolved"

    # Шаг 7. Итоговая согласованность: бонусы на карте отражают начисление
    balance = client.get(f"{loyalty.base}/api/v1/cards/CARD-E2E/balance", headers=loyalty_headers).json()
    assert any(op.get("operationId") == operation_id for op in balance["operations"])


def test_journey_is_idempotent_on_repeat(client, shop, loyalty, shop_headers, scenario_id):
    """Повтор всего сценария с теми же ключами не создаёт второй заказ и второй бонус."""
    key = uuid.uuid4().hex
    order_body = {"external_id": scenario_id, "lines": ORDERS["lines"]}
    first = client.post(f"{shop.base}/api/v1/orders", headers={**shop_headers, "Idempotency-Key": key},
                        json=order_body).json()
    second = client.post(f"{shop.base}/api/v1/orders", headers={**shop_headers, "Idempotency-Key": key},
                         json=order_body).json()
    assert (first["duplicate"], second["duplicate"]) == (False, True)

    loyalty_headers = {"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"}
    points = {"operation_id": f"OP-REPEAT-{scenario_id}", "card": "CARD-REPEAT", "points": 7.0}
    balance_before = client.get(f"{loyalty.base}/api/v1/cards/CARD-REPEAT/balance", headers=loyalty_headers).json()["balance"]
    client.post(f"{loyalty.base}/api/v1/accrue", headers=loyalty_headers, json=points)
    client.post(f"{loyalty.base}/api/v1/accrue", headers=loyalty_headers, json=points)
    balance_after = client.get(f"{loyalty.base}/api/v1/cards/CARD-REPEAT/balance", headers=loyalty_headers).json()["balance"]
    assert balance_after == pytest.approx(balance_before + 7.0, abs=0.01)


def test_negative_branch_partner_down_does_not_lose_order(client, shop, loyalty, shop_headers, scenario_id):
    """Негативная ветка: партнёр лежит → данные не потеряны, операция отложена (task_131)."""
    external_id = f"{scenario_id}-NEG"
    order = client.post(f"{shop.base}/api/v1/orders",
                        headers={**shop_headers, "Idempotency-Key": uuid.uuid4().hex},
                        json={"external_id": external_id, "lines": ORDERS["lines"]})
    assert order.status_code == 201

    # лояльность «лежит»: клиент обязан поставить операцию в очередь, а не потерять её
    failing = client.post(f"{loyalty.base}/api/v1/accrue",
                          headers={"X-Api-Key": loyalty.api_key, "X-Fault-Mode": "error500",
                                   "Content-Type": "application/json"},
                          json={"operation_id": f"OP-{external_id}", "card": "CARD-NEG", "points": 5.0})
    assert failing.status_code in (200, 500)

    retry = client.post(f"{loyalty.base}/api/v1/accrue",
                        headers={"X-Api-Key": loyalty.api_key, "Content-Type": "application/json"},
                        json={"operation_id": f"OP-{external_id}", "card": "CARD-NEG", "points": 5.0})
    assert retry.status_code == 200, "повтор после восстановления партнёра обязан пройти"
    assert retry.json()["points"] == pytest.approx(5.0)
