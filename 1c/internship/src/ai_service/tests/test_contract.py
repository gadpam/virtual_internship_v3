"""Контрактные тесты сервиса (task_232, task_140).

Проверяют: доступность, формат ответов, валидацию входных данных, единый формат ошибок.
Запуск: pytest -q
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_returns_ok():
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "version" in body


def test_stats_shape_matches_contract():
    response = client.get("/api/v1/stats")
    assert response.status_code == 200
    body = response.json()
    for field in ("service", "version", "index_vectors", "requests_total", "avg_latency_ms"):
        assert field in body


def test_search_rejects_too_short_query():
    response = client.post("/api/v1/search", json={"query": "а"})
    assert response.status_code == 422, "валидация Pydantic должна отклонить короткий запрос"


def test_search_returns_sources_with_score():
    response = client.post("/api/v1/search", json={"query": "остатки товаров на складах", "top_k": 3})
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body["results"], list)
    for item in body["results"]:
        assert 0.0 <= item["score"] <= 1.0
        assert item["chunk_id"]


def test_ask_returns_answer_or_honest_refusal():
    response = client.post("/api/v1/ask", json={"question": "Как оформить перемещение между складами?"})
    assert response.status_code == 200
    body = response.json()
    assert "answer" in body
    assert isinstance(body["sources"], list)
    assert body["refused"] in (True, False)
    if body["refused"]:
        assert body["sources"] == []


def test_correlation_id_is_propagated():
    response = client.get("/health", headers={"X-Correlation-Id": "test-correlation-123"})
    assert response.headers.get("X-Correlation-Id") == "test-correlation-123"


@pytest.mark.parametrize("top_k", [1, 5, 50])
def test_search_top_k_bounds(top_k):
    response = client.post("/api/v1/search", json={"query": "прайс поставщика", "top_k": top_k})
    assert response.status_code == 200
