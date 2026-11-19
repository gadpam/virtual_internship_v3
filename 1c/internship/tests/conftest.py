"""Общие фикстуры тестов стенда RIH.

Адреса сервисов берутся из переменных окружения, чтобы один и тот же набор тестов
работал и против локального docker-compose.test.yml, и против интеграционного
стенда (task_141, task_262).
"""
import os
from dataclasses import dataclass
from typing import Iterator

import pytest

try:
    import httpx
except ImportError:  # pragma: no cover - httpx объявлен в requirements.txt
    httpx = None


@dataclass(frozen=True)
class ServiceUrl:
    name: str
    base: str
    api_key: str

    @property
    def health(self) -> str:
        return f"{self.base}/health"


def _url(env_name: str, default: str) -> str:
    return os.getenv(env_name, default).rstrip("/")


@pytest.fixture(scope="session")
def shop() -> ServiceUrl:
    return ServiceUrl("shop", _url("RIH_SHOP_URL", "http://localhost:8020"),
                      os.getenv("MOCK_SHOP_API_KEY", "mock-shop-key"))


@pytest.fixture(scope="session")
def loyalty() -> ServiceUrl:
    return ServiceUrl("loyalty", _url("RIH_LOYALTY_URL", "http://localhost:8021"),
                      os.getenv("MOCK_LOYALTY_API_KEY", "mock-loyalty-key"))


@pytest.fixture(scope="session")
def tk() -> ServiceUrl:
    return ServiceUrl("tk", _url("RIH_TK_URL", "http://localhost:8022"),
                      os.getenv("MOCK_TK_API_KEY", "mock-tk-key"))


@pytest.fixture(scope="session")
def bank() -> ServiceUrl:
    return ServiceUrl("bank", _url("RIH_BANK_URL", "http://localhost:8023"), "")


@pytest.fixture(scope="session")
def tracker() -> ServiceUrl:
    return ServiceUrl("tracker", _url("RIH_TRACKER_URL", "http://localhost:8024"),
                      os.getenv("MOCK_TRACKER_API_KEY", "mock-tracker-key"))


@pytest.fixture(scope="session")
def ai_service() -> ServiceUrl:
    return ServiceUrl("ai", _url("RIH_AI_URL", "http://localhost:8010"),
                      os.getenv("AI_SERVICE_API_KEY", ""))


@pytest.fixture(scope="session")
def entrypoint() -> str:
    """Единая точка входа nginx (task_260)."""
    return _url("RIH_ENTRYPOINT_URL", "http://localhost:8080")


@pytest.fixture
def client() -> Iterator["httpx.Client"]:
    if httpx is None:
        pytest.skip("httpx не установлен: pip install -r requirements.txt")
    with httpx.Client(timeout=10.0) as session:
        yield session


@pytest.fixture
def shop_headers(shop: ServiceUrl) -> dict:
    return {"X-Api-Key": shop.api_key, "Content-Type": "application/json"}


def is_service_available(base: str) -> bool:
    if httpx is None:
        return False
    try:
        response = httpx.get(f"{base}/health", timeout=2.0)
        return response.status_code == 200
    except Exception:  # noqa: BLE001 - недоступность сервиса не должна ронять сбор тестов
        return False


@pytest.fixture(autouse=True)
def _isolate_tk_state(request, tk: ServiceUrl):
    """Интеграционные тесты не делят rate-limit окно ТК между собой."""
    stand_markers = {"integration", "e2e", "golden_path", "load"}
    if not stand_markers.intersection(m.name for m in request.node.iter_markers()) or httpx is None:
        return
    try:
        httpx.post(f"{tk.base}/__reset__", headers={"X-Api-Key": tk.api_key}, timeout=2.0)
    except Exception:  # noqa: BLE001 - стенд может быть недоступен, require_stand пропустит тест
        pass


@pytest.fixture
def require_stand(shop: ServiceUrl):
    """Пропускает тест, если учебный стенд не поднят."""
    if not is_service_available(shop.base):
        pytest.skip(
            f"стенд недоступен ({shop.base}). Поднимите: "
            "cd 1c/internship/tools && docker compose -f docker-compose.test.yml up -d --wait"
        )
