import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture
def client(tmp_path):
    """A TestClient backed by a throwaway SQLite file, one per test."""
    app = create_app(database_url=f"sqlite+pysqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as c:
        yield c
