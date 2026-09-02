"""FastAPI wiring for the database.

Kept separate from app.db so that module stays framework-free and usable from
the seed command, Alembic and scripts without importing FastAPI.
"""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session

from app.db import session_scope
from app.llm_client import LlmClient
from app.sms_client import SmsClient


def get_session(request: Request) -> Iterator[Session]:
    """Per-request session, committed on success and rolled back on error."""
    yield from session_scope(request.app.state.session_factory)


def get_sms_client(request: Request) -> SmsClient:
    """The outbound SMS client wired at app construction (real or recording)."""
    return request.app.state.sms_client


def get_llm_client(request: Request) -> LlmClient:
    """The Claude client wired at app construction (real or stub)."""
    return request.app.state.llm_client
