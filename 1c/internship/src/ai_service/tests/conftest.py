"""Общая подготовка тестов: переменные окружения для детерминированного прогона."""
import os

os.environ.setdefault("LLM_PROVIDER", "mock")
os.environ.setdefault("EMBEDDING_PROVIDER", "mock")
os.environ.setdefault("VECTOR_BACKEND", "memory")
os.environ.setdefault("KNOWLEDGE_BASE_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "..", "docs", "knowledge_base"))
os.environ.setdefault("SEARCH_MIN_SCORE", "0.0")
