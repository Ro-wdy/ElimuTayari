"""USSD browse flow (issue #2), tested at the /ussd HTTP seam.

Africa's Talking accumulates the caller's inputs into one text field joined
with "*", so a multi-step session is simulated by posting successive requests
with text "", "1", "1*2", ... under one sessionId. Assertions read the
plain-text CON/END body, the database rows the flow writes, and the recorded
SMS outbox - never a live Africa's Talking API.
"""

from typing import Iterator

import pytest

from app.db import create_db_engine, create_session_factory
from app.seed import seed_placeholder_content

PHONE = "+254711223344"


@pytest.fixture
def seeded_client(client, migrated_database_url) -> Iterator:
    """The conftest client, with the placeholder Mathematics content seeded."""
    engine = create_db_engine(migrated_database_url)
    session = create_session_factory(engine)()
    try:
        seed_placeholder_content(session)
        session.commit()
    finally:
        session.close()
        engine.dispose()
    yield client


def dial(client, text: str, session_id: str = "ATUid_1", phone: str = PHONE) -> str:
    response = client.post(
        "/ussd",
        data={
            "sessionId": session_id,
            "phoneNumber": phone,
            "networkCode": "63902",
            "serviceCode": "*384*1234#",
            "text": text,
        },
    )
    assert response.status_code == 200
    return response.text


def test_home_screen_lists_learning_areas_and_invites_code_entry(seeded_client):
    body = dial(seeded_client, "")

    assert body.startswith("CON ")
    assert "1. Mathematics" in body
    assert "code" in body.lower()
