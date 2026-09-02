"""Shared fixtures.

Test databases are built by running the real Alembic migrations rather than
Base.metadata.create_all, so the schema under test is the one that ships. A
create_all schema can drift from the migrations silently, which would make
these tests agree with the models while production disagrees with both.
"""

from pathlib import Path
from typing import Iterator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db import create_db_engine, create_session_factory
from app.main import create_app

SERVER_ROOT = Path(__file__).resolve().parents[1]


def run_migrations(database_url: str, revision: str = "head") -> None:
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.upgrade(config, revision)


def downgrade_migrations(database_url: str, revision: str = "base") -> None:
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    command.downgrade(config, revision)


@pytest.fixture
def database_url(tmp_path: Path) -> str:
    """URL of an empty, throwaway SQLite database. One per test."""
    return f"sqlite+pysqlite:///{tmp_path / 'test.db'}"


@pytest.fixture
def migrated_database_url(database_url: str) -> str:
    """URL of a throwaway database with the full schema applied."""
    run_migrations(database_url)
    return database_url


@pytest.fixture
def session(migrated_database_url: str) -> Iterator[Session]:
    """A session against the migrated schema, with foreign keys enforced."""
    engine = create_db_engine(migrated_database_url)
    session_factory = create_session_factory(engine)
    db_session = session_factory()
    try:
        yield db_session
    finally:
        db_session.rollback()
        db_session.close()
        engine.dispose()


@pytest.fixture
def client(migrated_database_url: str) -> Iterator[TestClient]:
    """A TestClient backed by the migrated throwaway database."""
    app = create_app(database_url=migrated_database_url)
    with TestClient(app) as test_client:
        yield test_client
