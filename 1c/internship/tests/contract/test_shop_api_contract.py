"""L2 · Контрактные тесты API онлайн-магазина (task_140).

Контракт — это обещание партнёра: какие поля, какого типа, какие коды ответов и
заголовки. Тесты падают, если mock-сервис (а значит и наша документация контракта)
разошёлся с реальностью. Именно этот уровень ловит «партнёр переименовал поле».
"""
import json
import uuid

import pytest

pytestmark = [pytest.mark.contract, pytest.mark.usefixtures("require_stand")]

PRODUCTS_REQUIRED_FIELDS = {"external_id", "sku", "name", "group", "price", "currency", "changed_at"}
ORDER_REQUIRED_FIELDS = {"external_id", "status", "total", "lines", "received_at"}


def test_health_is_open_and_reports_service_name(client, shop):
    response = client.get(shop.health)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "mock_shop_api"


def test_products_requires_api_key(client, shop):
    assert client.get(f"{shop.base}/api/v1/products").status_code == 401
    assert client.get(f"{shop.base}/api/v1/products",
                      headers={"X-Api-Key": "wrong"}).status_code == 403


def test_products_page_shape(client, shop, shop_headers):
    response = client.get(f"{shop.base}/api/v1/products", headers=shop_headers,
                          params={"limit": 5, "offset": 0})
    assert response.status_code == 200
    payload = response.json()

    assert set(payload) >= {"total", "limit", "offset", "items"}
    assert payload["limit"] == 5
    assert len(payload["items"]) <= 5
    for item in payload["items"]:
        assert PRODUCTS_REQUIRED_FIELDS.issubset(item), f"не хватает полей: {PRODUCTS_REQUIRED_FIELDS - set(item)}"
        assert isinstance(item["price"], (int, float))
        assert item["currency"] == "BYN"


def test_products_pagination_is_consistent(client, shop, shop_headers):
    first = client.get(f"{shop.base}/api/v1/products", headers=shop_headers,
                       params={"limit": 3, "offset": 0}).json()["items"]
    second = client.get(f"{shop.base}/api/v1/products", headers=shop_headers,
                        params={"limit": 3, "offset": 3}).json()["items"]
    assert [item["sku"] for item in first] != [item["sku"] for item in second]


def test_order_creation_returns_201_and_required_fields(client, shop, shop_headers):
    external_id = f"CONTRACT-{uuid.uuid4().hex[:8]}"
    response = client.post(f"{shop.base}/api/v1/orders", headers={**shop_headers, "Idempotency-Key": uuid.uuid4().hex},
                           json={"external_id": external_id,
                                 "lines": [{"sku": "SKU-00001", "quantity": 2, "price": 10.5}]})
    assert response.status_code == 201
    payload = response.json()
    assert ORDER_REQUIRED_FIELDS.issubset(payload)
    assert payload["externalId"] == external_id
    assert payload["status"] == "new"
    assert payload["total"] == pytest.approx(21.0)


def test_duplicate_order_without_idempotency_key_conflicts(client, shop, shop_headers):
    external_id = f"CONTRACT-DUP-{uuid.uuid4().hex[:8]}"
    body = {"external_id": external_id, "lines": [{"sku": "SKU-00001", "quantity": 1, "price": 5.0}]}
    first = client.post(f"{shop.base}/api/v1/orders", headers={**shop_headers, "Idempotency-Key": "key-1"}, json=body)
    assert first.status_code == 201

    second = client.post(f"{shop.base}/api/v1/orders", headers=shop_headers, json=body)
    assert second.status_code == 409


def test_idempotent_repeat_returns_same_result(client, shop, shop_headers):
    external_id = f"CONTRACT-IDEM-{uuid.uuid4().hex[:8]}"
    key = uuid.uuid4().hex
    body = {"external_id": external_id, "lines": [{"sku": "SKU-00002", "quantity": 3, "price": 7.25}]}
    headers = {**shop_headers, "Idempotency-Key": key}

    first = client.post(f"{shop.base}/api/v1/orders", headers=headers, json=body).json()
    second = client.post(f"{shop.base}/api/v1/orders", headers=headers, json=body).json()

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert first["externalId"] == second["externalId"]
    assert first["total"] == pytest.approx(second["total"])


def test_invalid_payload_is_rejected_with_422(client, shop, shop_headers):
    response = client.post(f"{shop.base}/api/v1/orders", headers=shop_headers,
                           json={"external_id": "BAD", "lines": [{"sku": "SKU-00001", "quantity": -1, "price": 5}]})
    assert response.status_code == 422


def test_status_transition_allowed_values(client, shop, shop_headers):
    external_id = f"CONTRACT-STATUS-{uuid.uuid4().hex[:8]}"
    client.post(f"{shop.base}/api/v1/orders", headers=shop_headers,
                json={"external_id": external_id, "lines": [{"sku": "SKU-00003", "quantity": 1, "price": 3.0}]})

    response = client.patch(f"{shop.base}/api/v1/orders/{external_id}/status",
                            headers=shop_headers, params={"status": "shipped"})
    assert response.status_code == 200
    assert response.json()["status"] == "shipped"


def test_unknown_order_returns_404_with_json(client, shop, shop_headers):
    response = client.patch(f"{shop.base}/api/v1/orders/NO-SUCH-ORDER/status",
                            headers=shop_headers, params={"status": "shipped"})
    assert response.status_code == 404
    assert "detail" in response.json()


@pytest.mark.parametrize("mode,expected", [
    ("error500", 500),
    ("rate429", 429),
])
def test_fault_modes_produce_documented_codes(client, shop, shop_headers, mode, expected):
    response = client.get(f"{shop.base}/api/v1/products",
                          headers={**shop_headers, "X-Fault-Mode": mode}, params={"limit": 1})
    assert response.status_code == expected
    if expected == 429:
        assert "retry-after" in {k.lower() for k in response.headers}


def test_retry_after_is_an_integer_number_of_seconds(client, shop, shop_headers):
    response = client.get(f"{shop.base}/api/v1/products",
                          headers={**shop_headers, "X-Fault-Mode": "rate429"}, params={"limit": 1})
    header = next((v for k, v in response.headers.items() if k.lower() == "retry-after"), None)
    assert header is not None
    assert int(header) > 0


def test_response_is_always_json_even_on_errors(client, shop, shop_headers):
    for mode in ("error500", "rate429"):
        response = client.get(f"{shop.base}/api/v1/products",
                              headers={**shop_headers, "X-Fault-Mode": mode}, params={"limit": 1})
        assert response.headers["content-type"].startswith("application/json")
        json.loads(response.text)
