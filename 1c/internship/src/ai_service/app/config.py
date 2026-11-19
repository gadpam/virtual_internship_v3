"""Настройки сервиса из переменных окружения (task_229, task_231, task_240)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    service_name: str = "rih-ai-service"
    service_version: str = "0.1.0"

    llm_provider: str = "mock"
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_model: str = ""
    llm_timeout_seconds: float = 20.0
    llm_max_retries: int = 2
    llm_temperature: float = 0.0

    embedding_provider: str = "mock"
    embedding_dim: int = 384

    vector_backend: str = "memory"
    vector_metric: str = "cosine"

    search_top_k: int = 5
    search_min_score: float = 0.35
    search_hybrid_enabled: bool = False
    rerank_enabled: bool = False

    knowledge_base_dir: str = "../../docs/knowledge_base"
    chunk_size: int = 900
    chunk_overlap: int = 150

    rate_limit_per_hour: int = 200
    monthly_budget_limit_usd: float = 20.0

    correlation_header: str = "X-Correlation-Id"


@lru_cache
def get_settings() -> Settings:
    """Единственная точка чтения настроек: так их легко подменить в тестах."""
    return Settings()
