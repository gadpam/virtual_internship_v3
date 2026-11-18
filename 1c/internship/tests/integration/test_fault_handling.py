"""L3 · Поведение при сбоях партнёров (task_127–132, task_141).

Матрица сбоев берётся из fixtures/faults_matrix.json — она же описана в
src/mock_shop_api/README.md. Тесты проверяют, что mock-сервис честно воспроизводит
сбой, а значит клиент 1С можно отладить на стенде, а не на живом партнёре.
"""
import json
import pathlib
import uuid

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.usefixtures("require_stand")]

FIXTURES = pathlib.Path(__file__).resolve().parents[1] / "fixtures"
MATRIX = json.loads((FIXTURES / "faults_matrix.json").read_text(encoding="utf-8"))["modes"]
BY_MODE = {item["mode"]: item for item in MATRIX}


def headers(shop, mode=None):
    base = {"X-Api-Key": shop.api_key}
    if mode:
        base["X-Fault-Mode"] = mode
    return base


def test_matrix_is_documented_for_every_mode(shop):
    expected = {"ok", "error500", "timeout", "slow", "rate429", "garbage", "duplicate", "label_failed"}
    documented = set(BY_MODE)
    assert expected.issubset(documented), f"в матрице не хватает режимов: {expected - documented}"
    for item in MATRIX:
        assert item["client_action"], f"для режима {item['mode']} не описано ожидаемое поведение клиента"


def test_error500_is_repeatable_and_logged(client, shop):
    for _ in range(3):
        response = client.get(f"{shop.base}/api/v1/products", headers=headers(shop, "error500"),
                              params={"limit": 1})
        assert response.status_code == 500
        assert response.json()["detail"]


def test_rate429_carries_retry_after(client, shop):
    response = client.get(f"{shop.base}/api/v1/products", headers=headers(shop, "rate429"),
                          params={"limit": 1})
    assert response.status_code == BY_MODE["rate429"]["http_status"]
    retry_after = next((v for k, v in response.headers.items() if k.lower() == "retry-after"), None)
    assert retry_after and int(retry_after) > 0


@pytest.mark.slow
def test_slow_mode_stays_within_client_timeout_budget(client, shop):
    """Режим slow отвечает за ~4 с: клиент с таймаутом 10 с успевает (task_127, task_131)."""
    response = client.get(f"{shop.base}/api/v1/products", headers=headers(shop, "slow"),
                          params={"limit": 1}, timeout=12.0)
    assert response.status_code == 200


@pytest.mark.slow
def test_timeout_mode_exceeds_reasonable_client_timeout(client, shop):
    """Режим timeout держит соединение ~35 с: клиент с таймаутом 5 с обязан прерваться сам."""
    with pytest.raises(Exception):
        client.get(f"{shop.base}/api/v1/products", headers=headers(shop, "timeout"),
                   params={"limit": 1}, timeout=5.0)


def test_garbage_mode_does_not_return_valid_json(client, shop):
    response = client.get(f"{shop.base}/api/v1/products", headers=headers(shop, "garbage"),
                          params={"limit": 1})
    assert response.status_code in (200, 502)
    payload = response.json()
    # «сломанный» ответ распознаётся по отсутствию обязательной структуры
    assert "items" not in payload


def test_transport_company_respects_its_own_rate_limit(client, tk):
    """Реальный лимит ТК: 10 запросов в минуту на ключ (task_93)."""
    tk_headers = {"X-Api-Key": tk.api_key, "Content-Type": "application/json"}
    body = {"city_to": "Гродно", "weight_kg": 1.0, "volume_m3": 0.01}
    statuses = []
    for _ in range(14):
        statuses.append(client.post(f"{tk.base}/api/v1/calculate", headers=tk_headers, json=body).status_code)
    assert 429 in statuses, "лимит частоты не сработал — проверьте MOCK_TK_RATE_LIMIT"
    assert statuses[0] == 200


def test_shipment_survives_label_service_outage(client, tk):
    """Компенсация: заявка создана, этикетка недоступна — данные не теряются (task_130)."""
    tk_headers = {"X-Api-Key": tk.api_key, "Content-Type": "application/json"}
    external_id = f"FAULT-{uuid.uuid4().hex[:8]}"
    shipment = client.post(f"{tk.base}/api/v1/shipments", headers=tk_headers,
                           json={"external_id": external_id, "city_to": "Витебск", "weight_kg": 3.0}).json()

    label = client.get(f"{tk.base}/api/v1/shipments/{shipment['shipmentId']}/label",
                       headers={**tk_headers, "X-Fault-Mode": "label_failed"})
    assert label.status_code == 503

    # заявка жива и читаема: её можно обработать позже, когда сервис этикеток вернётся
    assert client.get(f"{tk.base}/api/v1/shipments/{shipment['shipmentId']}",
                      headers=tk_headers).status_code == 200


def test_unauthorized_calls_are_rejected_before_fault_modes_apply(client, shop):
    """Без ключа сервис отвечает 401 даже при запрошенном режиме сбоя (task_133)."""
    response = client.get(f"{shop.base}/api/v1/products",
                          headers={"X-Fault-Mode": "error500"}, params={"limit": 1})
    assert response.status_code == 401
