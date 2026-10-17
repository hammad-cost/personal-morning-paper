import pytest
from fastapi.testclient import TestClient

from app import store
from app.main import app


@pytest.fixture(autouse=True)
def temp_store(tmp_path, monkeypatch):
    """Point the store at a temp file so tests never touch data/store.json."""
    path = tmp_path / "store.json"
    monkeypatch.setattr(store, "STORE_PATH", path)
    return path


@pytest.fixture
def client():
    return TestClient(app)
