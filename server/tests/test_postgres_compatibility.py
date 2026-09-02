"""Postgres compatibility.

Development runs on SQLite and production on Postgres, so "Postgres-compatible"
needs to be checked rather than asserted. Most of it can be checked without a
server: Alembic's offline mode renders the migration as static SQL for a chosen
dialect, which catches types and constructs that have no Postgres spelling.

What that cannot catch is runtime behaviour, so test_migrations_and_seed_run
runs the real thing against whatever POSTGRES_TEST_URL points at, and skips
when it is unset. Issue #10 sets it against the production-shaped database.
"""

import contextlib
import io
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.db import create_db_engine, create_session_factory
from app.models import Base
from app.seed import seed_placeholder_content
from tests.conftest import SERVER_ROOT, run_migrations

POSTGRES_URL = "postgresql+psycopg://user:password@localhost:5432/elimutayari"

EXPECTED_TABLES = {
    "substrands",
    "teachers",
    "content_units",
    "teaching_sessions",
    "questions",
    "tests",
}


def render_migration_sql(database_url: str) -> str:
    """The migration as static SQL for the given URL's dialect, no server needed."""
    config = Config(str(SERVER_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(SERVER_ROOT / "migrations"))
    config.set_main_option("sqlalchemy.url", database_url)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        command.upgrade(config, "head", sql=True)
    return buffer.getvalue()


@pytest.fixture(scope="module")
def postgres_ddl() -> str:
    return render_migration_sql(POSTGRES_URL)


def test_migration_renders_every_table_as_postgres_ddl(postgres_ddl: str):
    created = {
        line.split()[2] for line in postgres_ddl.splitlines() if line.startswith("CREATE TABLE")
    }

    assert EXPECTED_TABLES <= created


def test_autoincrement_keys_become_serial_on_postgres(postgres_ddl: str):
    """content_units, teaching_sessions, questions and tests each have one."""
    assert postgres_ddl.count("SERIAL") == 4


def test_timestamps_keep_their_timezone_on_postgres(postgres_ddl: str):
    """teachers.created_at, teaching_sessions.taught_at, questions.created_at
    and tests.sent_at, so scheduling and analytics are not left guessing."""
    assert postgres_ddl.count("TIMESTAMP WITH TIME ZONE") == 4


def test_structured_columns_become_postgres_json(postgres_ddl: str):
    """tests.substrand_codes and tests.items_json."""
    assert postgres_ddl.count(" JSON") == 2


def test_check_constraints_survive_with_their_names(postgres_ddl: str):
    """Named so Alembic can later ALTER them; unnamed ones cannot be altered."""
    assert "CONSTRAINT ck_content_units_kind_valid" in postgres_ddl
    assert "CONSTRAINT ck_questions_source_valid" in postgres_ddl


@pytest.mark.parametrize("artifact", ["AUTOINCREMENT", "DATETIME", "PRAGMA"])
def test_postgres_ddl_contains_no_sqlite_artifacts(postgres_ddl: str, artifact: str):
    assert artifact not in postgres_ddl.upper()


def test_every_model_compiles_against_the_postgres_dialect():
    """Catches a column type with no Postgres mapping at the model level, even
    if no migration has been generated for it yet."""
    dialect = postgresql.dialect()

    for table in Base.metadata.sorted_tables:
        assert str(CreateTable(table).compile(dialect=dialect))


@pytest.mark.skipif(
    not os.environ.get("POSTGRES_TEST_URL"),
    reason="POSTGRES_TEST_URL is unset; no live database to run against",
)
def test_migrations_and_seed_run_against_a_live_database():
    """The runtime half that static SQL cannot prove. Runs wherever
    POSTGRES_TEST_URL points, which issue #10 sets to real Postgres."""
    database_url = os.environ["POSTGRES_TEST_URL"]
    run_migrations(database_url)

    engine = create_db_engine(database_url)
    try:
        assert EXPECTED_TABLES <= set(inspect(engine).get_table_names())

        session = create_session_factory(engine)()
        try:
            first = seed_placeholder_content(session)
            session.commit()
            second = seed_placeholder_content(session)
            session.commit()
        finally:
            session.close()
    finally:
        engine.dispose()

    assert first.substrands_created == 15
    assert second.substrands_created == 0
    assert second.substrands_updated == 15
