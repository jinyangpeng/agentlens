"""pytest 公共 fixtures。"""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.dependencies import get_repository
from app.repositories.memory import InMemoryRepository


@pytest.fixture
def memory_repo() -> InMemoryRepository:
    return InMemoryRepository()


@pytest.fixture
def client(memory_repo) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_repository] = lambda: memory_repo
    return TestClient(app)
