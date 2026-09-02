"""Test generation via Claude (issue #8), tested at the /ussd HTTP seam.

A teacher picks "Get a test" from the home screen, navigates the same
area/strand/sub-strand menu, and the route asks Claude (through the LlmClient
seam) for ~5 questions composed from the sub-strand's guidance content and
its question bank, delivers them by SMS, and stores a tests row. Sessions are
simulated as in test_ussd_browse: successive posts of the accumulated text,
asserting on the CON/END body, the database rows, the recorded SMS outbox and
the recorded Claude prompts - never a live API.
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


def teach(client, text: str = "1*1*2", session_id: str = "ATUid_taught") -> None:
    """Complete one browse-and-select session so PHONE becomes a known teacher."""
    body = dial(client, text, session_id=session_id)
    assert body.startswith("END ")


def test_first_time_home_offers_get_a_test_after_the_learning_areas(seeded_client):
    body = dial(seeded_client, "")

    assert body.startswith("CON ")
    assert "1. Mathematics" in body
    assert "2. Get a test" in body


def test_returning_home_offers_get_a_test_after_the_teacher_options(seeded_client):
    teach(seeded_client)

    body = dial(seeded_client, "", session_id="ATUid_2")

    assert body.startswith("CON ")
    assert "1. Continue: Formulae and Variations" in body
    assert "3. My coverage" in body
    assert "4. Upload questions" in body
    assert "5. Get a test" in body


def test_get_a_test_reuses_the_area_strand_substrand_navigation(seeded_client):
    body = dial(seeded_client, "2")
    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "Get a test" in body
    assert "1. Mathematics" in body

    body = dial(seeded_client, "2*1")
    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "1. Algebra" in body

    body = dial(seeded_client, "2*1*1")
    assert body.startswith("CON ")
    assert "Invalid" not in body
    assert "2. Formulae and Variations" in body


def test_get_a_test_navigation_works_from_the_returning_home(seeded_client):
    teach(seeded_client)

    body = dial(seeded_client, "5", session_id="ATUid_2")
    assert body.startswith("CON ")
    assert "Get a test" in body
    assert "1. Mathematics" in body


def test_invalid_choice_on_the_test_area_screen_re_prompts(seeded_client):
    body = dial(seeded_client, "2*9")

    assert body.startswith("CON ")
    assert "Invalid" in body
    assert "1. Mathematics" in body
