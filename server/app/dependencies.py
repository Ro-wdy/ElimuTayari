"""FastAPI wiring for the database.

Kept separate from app.db so that module stays framework-free and usable from
the seed command, Alembic and scripts without importing FastAPI.
"""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.db import session_scope


def get_session(request: Request) -> Iterator[Session]:
    """Per-request session, committed on success and rolled back on error."""
    yield from session_scope(request.app.state.session_factory)
